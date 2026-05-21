"""OCR provider package — public exports."""

from app.services.ocr.base import BaseOCRProvider
from app.services.ocr.tesseract import TesseractProvider
from app.services.ocr.types import ExtractedAnswer, ExtractedQuestion, OCRResult

__all__ = [
    "BaseOCRProvider",
    "ExtractedAnswer",
    "ExtractedQuestion",
    "OCRResult",
    "TesseractProvider",
]
