import os
import json
import time
import mimetypes
import io
import concurrent.futures
import argparse
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

# --- Configuration ---
# Load environment variables from .env file
load_dotenv()

API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

# Initialize Client
client = None
if API_KEY:
    client = genai.Client(api_key=API_KEY)
else:
    # Don't exit on import, just warn
    print("Warning: GOOGLE_API_KEY or GEMINI_API_KEY not found in environment. API calls will fail until configured.")

MODEL_NAME = 'gemini-3-pro-image-preview' # Or appropriate model
OUTPUT_BASE = os.environ.get("OUTPUT_DIR", "./output")
TASKS_FILE = "tasks.json"

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

def generate_image_content(prompt, output_path, base_image=None):
    print(f"Generating {'Dirty' if base_image else 'Clean'}: {output_path}...")
    
    parts = [types.Part.from_text(text=prompt)]
    
    if base_image:
        # If we have a base image (PIL Image), convert to bytes for the API
        try:
            img_byte_arr = io.BytesIO()
            base_image.save(img_byte_arr, format=base_image.format or 'PNG')
            img_bytes = img_byte_arr.getvalue()
            parts.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
        except Exception as e:
            print(f"Error processing base image for {output_path}: {e}")
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

def process_task(task, dirty_only=False):
    subdir = task["subdir"]
    clean_name = task["clean_file"]
    dirty_name = task["dirty_file"]
    
    clean_path = os.path.join(OUTPUT_BASE, subdir, clean_name)
    dirty_path = os.path.join(OUTPUT_BASE, subdir, dirty_name)
    
    print(f"Starting task pair: {clean_name}")
    
    clean_img_obj = None

    # 1. Handle Clean Image
    if dirty_only:
        if os.path.exists(clean_path):
            print(f"Loading existing clean image for context: {clean_path}")
            try:
                clean_img_obj = Image.open(clean_path)
            except Exception as e:
                print(f"Error loading existing clean image {clean_path}: {e}")
                return # Cannot proceed without base image
        else:
            print(f"Warning: Clean image not found at {clean_path}. generating it regardless of flag.")
            clean_img_obj = generate_image_content(task["clean_prompt"], clean_path)
    else:
        # Generate new clean image
        clean_img_obj = generate_image_content(task["clean_prompt"], clean_path)
    
    if clean_img_obj:
        # 2. Generate Dirty using Clean as context
        # We pass the PIL image object directly to our helper function
        generate_image_content(task["dirty_prompt"], dirty_path, base_image=clean_img_obj)
    
    time.sleep(5)
    return clean_name

def main():
    parser = argparse.ArgumentParser(description="Generate Before/After images for Raindrop Web.")
    parser.add_argument("--dirty-only", action="store_true", help="Only regenerate the dirty image, using the existing clean image as context.")
    parser.add_argument("--task", type=str, help="Filter tasks by name (case-insensitive substring match).")
    args = parser.parse_args()

    print("Starting image generation...")
    if args.dirty_only:
        print("Mode: Dirty Only (reusing existing clean images)")
    if args.task:
        print(f"Filter: Processing tasks matching '{args.task}'")

    print(f"Reading tasks from: {TASKS_FILE}")
    
    try:
        with open(TASKS_FILE, 'r') as f:
            all_tasks = json.load(f)
    except FileNotFoundError:
        print(f"Error: {TASKS_FILE} not found.")
        return

    # Filter tasks based on arguments
    tasks_to_process = []
    if args.task:
        filter_str = args.task.lower()
        for task in all_tasks:
            # Check matches in subdir, clean_file, or prompts as a proxy for "task name"
            if (filter_str in task["subdir"].lower() or 
                filter_str in task["clean_file"].lower() or
                filter_str in task.get("clean_prompt", "").lower()):
                tasks_to_process.append(task)
    else:
        tasks_to_process = all_tasks

    if not tasks_to_process:
        print("No tasks found matching the criteria.")
        return

    print(f"Processing {len(tasks_to_process)} tasks...")

    # Use ThreadPoolExecutor for concurrency
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        # Pass the dirty_only flag to process_task
        futures = {executor.submit(process_task, task, args.dirty_only): task for task in tasks_to_process}
        
        for future in concurrent.futures.as_completed(futures):
            task = futures[future]
            try:
                result = future.result()
                print(f"Completed task set for: {task['clean_file']}")
            except Exception as exc:
                print(f"Task generated an exception: {exc}")

if __name__ == "__main__":
    main()
