"""
Image ingestion: runs OCR (pytesseract) to extract any visible text (useful for
screenshots/diagrams with labels), and keeps the file path so a vision-capable
local model (e.g. Ollama's llava) can be called directly at query time for
questions like "explain this architecture diagram."
"""
import pytesseract
from PIL import Image
from app.config import settings

if settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD


def load_image(path: str) -> list[dict]:
    docs = []
    try:
        img = Image.open(path)
        ocr_text = pytesseract.image_to_string(img).strip()
    except Exception:
        ocr_text = ""

    text = ocr_text if ocr_text else "[No machine-readable text detected in this image. " \
                                       "It will be analyzed directly by the vision model at query time.]"
    docs.append({
        "text": text,
        "location": "image",
        "page": None,
        "image_path": path,
    })
    return docs
