"""Abstract base class for OCR providers."""

from abc import ABC, abstractmethod
from pathlib import Path

from PIL import Image

from app.services.ocr.types import OCRResult


class BaseOCRProvider(ABC):
    """Abstract base class that all OCR providers must implement."""

    @abstractmethod
    async def extract_from_path(self, file_path: Path) -> OCRResult:
        """Extract text/structure from a file on disk.

        Args:
            file_path: Path to image or PDF file.

        Returns:
            OCRResult with extracted text and structured questions.
        """
        ...

    @abstractmethod
    async def extract_from_image(self, image: Image.Image) -> OCRResult:
        """Extract text/structure from a PIL Image object.

        Args:
            image: PIL Image object.

        Returns:
            OCRResult with extracted text and structured questions.
        """
        ...

    @abstractmethod
    def health_check(self) -> dict:
        """Return provider health status.

        Returns:
            Dict with health information (e.g. {"status": "ok", "engine": "tesseract"}).
        """
        ...

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Return the provider's identifier string."""
        ...
