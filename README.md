# Image Generator

A utility to generate Before/After images using Google's Gemini models.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configuration**:
    Copy `.env.example` to `.env` and fill in your details:
    ```bash
    cp .env.example .env
    ```
    - `GOOGLE_API_KEY`: Your Google Gemini API key.
    - `OUTPUT_DIR`: Directory where images will be saved (default: `./output`).

## Usage

Run the script to generate images based on `tasks.json`:

```bash
python generate_images.py
```

### Options

- `--dirty-only`: Only regenerate the 'dirty' (before) image, using the existing 'clean' (after) image as context.
- `--task <name>`: Filter tasks by name (case-insensitive substring match).

Example:
```bash
python generate_images.py --task "hero"
```
