"""OCR — Extrai texto de imagens usando Tesseract."""

import os

from langchain.tools import tool


@tool("read_latest_screenshot", return_direct=True)
def read_text_from_latest_image(image_path: str | None = None) -> str:
    """
    Reads and extracts text from an image file using OCR (Tesseract).
    Use this tool when the user says something like:
    - "Read the screen"
    - "What does the screenshot say?"
    - "Extract text from the image"
    """
    if image_path is None:
        image_path = os.getenv("AURION_SCREENSHOT_PATH", os.path.expanduser("./screenshot.png"))

    if not os.path.exists(image_path):
        return f"Image not found at {image_path}."

    try:
        from PIL import Image
        import pytesseract

        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text.strip() if text else "No readable text found in the image."
    except ImportError as e:
        return f"OCR dependencies not installed: {e}. Install Pillow and pytesseract."
    except Exception as e:
        return f"Failed to extract text: {str(e)}"
