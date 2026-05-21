"""OCR Service — thin compatibility shim delegating to TesseractProvider.

This module preserves backward compatibility for existing callers that import
OCRService from app.services.ocr_service. All logic has been extracted into
TesseractProvider (app/services/ocr/tesseract.py).
"""

from pathlib import Path
from typing import BinaryIO

from PIL import Image

from app.services.ocr.tesseract import TesseractProvider
from app.services.ocr.types import OCRResult


class OCRService:
    """Backward-compatible shim that delegates to TesseractProvider.

    All OCR logic now lives in TesseractProvider. This class exists solely
    to preserve existing import paths and method signatures.
    """

    def __init__(self, tesseract_cmd: str | None = None, lang: str | None = None):
        """Initialize OCR service.

        Args:
            tesseract_cmd: Path to tesseract binary (optional, uses settings if not provided)
            lang: Language code (optional, uses settings if not provided)
        """
        self._provider = TesseractProvider(tesseract_cmd=tesseract_cmd, lang=lang)

    async def extract_text(
        self,
        file_data: BinaryIO,
        preprocess: bool = True,
    ) -> OCRResult:
        """Extract text from image file.

        Args:
            file_data: Binary file data
            preprocess: Whether to apply image preprocessing

        Returns:
            OCRResult with extracted text and questions
        """
        return await self._provider.extract_text(file_data, preprocess)

    async def extract_from_path(self, file_path: Path) -> OCRResult:
        """Extract text from image or PDF file path.

        Args:
            file_path: Path to image or PDF file

        Returns:
            OCRResult with extracted text
        """
        return await self._provider.extract_from_path(file_path)

    async def extract_text_from_image(
        self, image: Image.Image, preprocess: bool = True
    ) -> OCRResult:
        """Extract text from PIL Image using OCR.

        Args:
            image: PIL Image object
            preprocess: Whether to apply image preprocessing

        Returns:
            OCRResult with extracted text
        """
        return await self._provider.extract_from_image(image, preprocess)

    def get_confidence_level(self, confidence: float) -> str:
        """Get confidence level description.

        Args:
            confidence: Confidence score (0-100)

        Returns:
            Level description: "high", "medium", or "low"
        """
        return self._provider.get_confidence_level(confidence)
