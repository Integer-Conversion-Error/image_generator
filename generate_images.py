import os
import io
import json
import argparse
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

# --- Configuration ---
# Load environment variables from .env file
load_dotenv()

API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "./output")

# Initialize Client
client = None
if API_KEY:
    client = genai.Client(api_key=API_KEY)
else:
    # Don't exit on import, just warn
    print("Warning: GOOGLE_API_KEY or GEMINI_API_KEY not found in environment. API calls will fail until configured.")

MODEL_NAME = 'gemini-3-pro-image-preview' # Or appropriate model

def save_image_from_part(part, output_path):
    if part.inline_data and part.inline_data.data:
        try:
            data = part.inline_data.data
            # Convert bytes to PIL Image to verify/save correctly
            image = Image.open(io.BytesIO(data))
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            image.save(output_path)
            print(f"Saved to {output_path}")
            return image
        except Exception as e:
            print(f"Error saving image content for {output_path}: {e}")
    return None

def generate_image_content(prompt, output_path, base_images=None):
    print(f"Generating image: {output_path}...")
    
    parts = [types.Part.from_text(text=prompt)]
    
    if base_images:
        if not isinstance(base_images, list):
            base_images = [base_images]
        for base_image in base_images:
            # If we have base images (PIL Images), convert to bytes for the API
            try:
                img_byte_arr = io.BytesIO()
                base_image.save(img_byte_arr, format=base_image.format or 'PNG')
                img_bytes = img_byte_arr.getvalue()
                parts.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
            except Exception as e:
                print(f"Error processing base image: {e}")
                return None

    contents = [
        types.Content(
            role="user",
            parts=parts,
        ),
    ]

    generate_content_config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(
            image_size="1K", # Keeping standard size
        ),
        # Using Google Search tool often helps context but might not be strictly needed for pure generation
        # tools=[types.Tool(google_search=types.GoogleSearch())], 
    )

    try:
        # We only expect one image per request for this flow
        # Using generate_content_stream as per user example to handle potential chunking
        for chunk in client.models.generate_content_stream(
            model=MODEL_NAME,
            contents=contents,
            config=generate_content_config,
        ):
            if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                for part in chunk.candidates[0].content.parts:
                    saved_img = save_image_from_part(part, output_path)
                    if saved_img:
                        return saved_img
        
        print(f"No valid image content returned for: {output_path}")
        return None

    except Exception as e:
        print(f"Failed to generate {output_path}: {e}")
        return None

def load_tasks(tasks_file="tasks.json"):
    with open(tasks_file, 'r') as f:
        return json.load(f)

def generate_task_images(task, dirty_only=False):
    subdir = task.get("subdir", "")
    output_base = os.path.join(OUTPUT_DIR, subdir)
    os.makedirs(output_base, exist_ok=True)
    
    clean_path = os.path.join(output_base, task["clean_file"])
    dirty_path = os.path.join(output_base, task["dirty_file"])
    
    if not dirty_only:
        # Generate clean image
        generate_image_content(task["clean_prompt"], clean_path)
    
    # Generate dirty image, using clean as base if it exists
    base_image = None
    if os.path.exists(clean_path):
        try:
            base_image = Image.open(clean_path)
        except:
            pass
    generate_image_content(task["dirty_prompt"], dirty_path, base_image)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate before/after images using Gemini API")
    parser.add_argument("--dirty-only", action="store_true", help="Only regenerate the 'dirty' (before) image, using the existing 'clean' (after) image as context")
    parser.add_argument("--task", type=str, help="Filter tasks by name (case-insensitive substring match)")
    
    args = parser.parse_args()
    
    if not client:
        print("Error: API key not configured. Please set GOOGLE_API_KEY in .env file.")
        exit(1)
    
    tasks = load_tasks()
    
    for task in tasks:
        task_name = task.get("clean_file", "").replace("-clean", "").replace(".png", "").replace(".jpeg", "").replace(".jpg", "")
        if args.task and args.task.lower() not in task_name.lower():
            continue
        print(f"Processing task: {task_name}")
        generate_task_images(task, args.dirty_only)
