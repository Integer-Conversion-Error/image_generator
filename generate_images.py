import os
import io
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
    print(f"Generating image: {output_path}...")
    
    parts = [types.Part.from_text(text=prompt)]
    
    if base_image:
        # If we have a base image (PIL Image), convert to bytes for the API
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
