import logging
import os

from pdf2image import convert_from_path
import pytesseract

logger = logging.getLogger(__name__)

POPPLER_BIN = os.environ.get("POPPLER_BIN", r"C:/poppler-24.08.0/Library/bin")
TESSERACT_BIN = os.environ.get("TESSERACT_BIN", r"C:/Program Files/Tesseract-OCR/tesseract.exe")

if POPPLER_BIN and POPPLER_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] += os.pathsep + POPPLER_BIN

# Try to configure tesseract, but don't fail if it's not available
try:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_BIN
except Exception as exc:
    logger.warning("Could not configure Tesseract: %s", exc)


def extract_text_from_image_pdf(file_path):
    try:
        images = convert_from_path(file_path, dpi=300)
        full_text = ""
        for image in images:
            try:
                text = pytesseract.image_to_string(image, lang="vie")
                full_text += text + "\n"
            except Exception as exc:
                logger.warning("Could not extract text from image: %s", exc)
                continue

        upper_text = full_text.upper()
        if "KẾT LUẬN" in upper_text:
            start = upper_text.find("KẾT LUẬN") + len("KẾT LUẬN")
            after_conclusion = full_text[start:].strip()
            upper_after = after_conclusion.upper()
            end = upper_after.find("ĐỀ NGHỊ")
            if end != -1:
                return after_conclusion[:end].strip()
            return after_conclusion.split("\n")[0].strip()

        return "Không tìm thấy phần kết luận."
    except Exception as exc:
        logger.error("Error extracting text from PDF: %s", exc)
        return str(exc)