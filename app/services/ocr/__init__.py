"""OCR provider package — public exports."""

from app.services.ocr.base import BaseOCRProvider
from app.services.ocr.types import ExtractedAnswer, ExtractedQuestion, OCRResult
from app.services.ocr.tesseract import TesseractProvider
from app.services.ocr.openai_vision import OpenAIVisionProvider
from app.services.ocr.factory import OCRProviderFactory, get_ocr_provider

__all__ = [
    "BaseOCRProvider",
    "TesseractProvider",
    "OpenAIVisionProvider",
    "OCRProviderFactory",
    "get_ocr_provider",
    "OCRResult",
    "ExtractedQuestion",
    "ExtractedAnswer",
]
