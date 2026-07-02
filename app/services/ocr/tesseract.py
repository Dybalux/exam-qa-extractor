"""Tesseract OCR provider implementation."""

import logging
import re
import string
from pathlib import Path
from typing import BinaryIO

import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter

from app.config import get_settings
from app.core.constants import CONFIDENCE_HIGH, CONFIDENCE_LOW, CONFIDENCE_MEDIUM
from app.core.exceptions import OCRProcessingError
from app.services.ocr.base import BaseOCRProvider
from app.services.ocr.types import ExtractedQuestion, OCRResult

logger = logging.getLogger(__name__)
settings = get_settings()

# Configure Tesseract
pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


class TesseractProvider(BaseOCRProvider):
    """Tesseract-based OCR provider.

    Encapsulates all current OCRService Tesseract/pytesseract logic.
    """

    def __init__(self, tesseract_cmd: str | None = None, lang: str | None = None):
        """Initialize Tesseract provider.

        Args:
            tesseract_cmd: Path to tesseract binary (optional, uses settings if not provided)
            lang: Language code (optional, uses settings if not provided)
        """
        self.tesseract_cmd = tesseract_cmd or settings.tesseract_cmd
        self.lang = lang or settings.tesseract_lang
        self._check_tesseract()

    @property
    def engine_name(self) -> str:
        """Return the provider's identifier string."""
        return "tesseract"

    def _check_tesseract(self) -> None:
        """Check if Tesseract is installed."""
        try:
            pytesseract.get_tesseract_version()
        except Exception as e:
            logger.warning(f"Tesseract not found or not configured: {e}")
            raise OCRProcessingError(
                "Tesseract OCR is not installed. Please install Tesseract and configure TESSERACT_CMD."
            )

    def health_check(self) -> dict:
        """Return provider health status."""
        try:
            pytesseract.get_tesseract_version()
            return {"status": "ok", "engine": self.engine_name}
        except Exception as e:
            return {"status": "error", "engine": self.engine_name, "error": str(e)}

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image for better OCR results.

        Args:
            image: PIL Image object

        Returns:
            Preprocessed image
        """
        # Convert to grayscale
        img = image.convert("L")

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        # Denoise
        img = img.filter(ImageFilter.MedianFilter(size=3))

        return img

    def _detect_code_blocks(self, text: str) -> bool:
        """Detect if text contains code blocks or pseudocode.

        Args:
            text: Extracted text

        Returns:
            True if code blocks detected
        """
        code_indicators = [
            r"\b(int|char|float|double|void|struct|class)\b",  # Type declarations
            r"\b(if|for|while|do|switch|case|break|return)\b",  # Control flow
            r"[{};]",  # Braces and semicolons
            r"\b(pid|fork|wait|exec|pipe)\b",  # OS-specific keywords
            r"\b(pthread_|mutex_|sem_|signal_)\b",  # Threading/synchronization
        ]

        for pattern in code_indicators:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _detect_symbols(self, text: str) -> list[str]:
        """Detect technical symbols that may need special handling.

        Args:
            text: Extracted text

        Returns:
            List of detected symbols
        """
        # Common OS symbols that OCR struggles with
        symbols = []
        symbol_patterns = [
            (r"\|", "pipe"),
            (r"&", "ampersand/address"),
            (r"\*", "asterisk/pointer"),
            (r"->", "arrow operator"),
            (r"&&", "logical AND"),
            (r"\|\|", "logical OR"),
            (r"==", "equality"),
            (r"!=", "not equal"),
        ]

        for pattern, name in symbol_patterns:
            if re.search(pattern, text):
                symbols.append(name)

        return symbols

    def _segment_questions(self, text: str) -> list[tuple[int, str, float]]:
        """Segment text into individual questions.

        Args:
            text: Full OCR text

        Returns:
            List of tuples (order, text, confidence)
        """
        questions = []

        # Pattern to match question numbers (1., 1), (1), etc.)
        patterns = [
            r"(?:^|\n)\s*(\d+)\s*[.\)]\s*",  # 1. or 1)
            r"(?:^|\n)\s*Pregunta\s+(\d+)[:\.]\s*",  # "Pregunta 1:"
        ]

        # Try to find question boundaries
        matches = []
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matches.append((int(match.group(1)), match.start()))

        if not matches:
            # No numbered questions found, treat as single question
            confidence = self._estimate_confidence(text)
            return [(1, text.strip(), confidence)]

        # Sort by position
        matches.sort(key=lambda x: x[1])

        # Extract question text
        for i, (num, start) in enumerate(matches):
            end = matches[i + 1][1] if i + 1 < len(matches) else len(text)
            question_text = text[start:end].strip()
            confidence = self._estimate_confidence(question_text)
            questions.append((num, question_text, confidence))

        return questions

    def _estimate_confidence(self, text: str) -> float:
        """Estimate OCR confidence based on heuristics.

        Args:
            text: Extracted text

        Returns:
            Estimated confidence score (0-100)
        """
        score = 100.0

        # Penalize for garbled characters (non-alphanumeric, non-whitespace, non-punctuation)
        # Allow: word chars, whitespace, and punctuation
        allowed_chars = set(
            string.ascii_letters
            + string.digits
            + string.whitespace
            + string.punctuation
            + "áéíóúÁÉÍÓÚñÑüÜ"
        )
        garbled_chars = sum(1 for char in text if char not in allowed_chars)
        score -= garbled_chars * 2

        # Penalize for very short text (likely extraction error)
        words = text.split()
        if len(words) < 5:
            score -= 30

        # Penalize for excessive newlines (formatting issues)
        newline_count = text.count("\n")
        if newline_count > len(words) / 3:
            score -= 10

        # Check for common OCR errors
        common_errors = ["1l", "0O", "rn"]
        for error in common_errors:
            if error in text:
                score -= 5

        return max(0.0, min(100.0, score))

    def _extract_text_from_pdf_direct(self, file_path: Path) -> str | None:
        """Try to extract text directly from PDF (no OCR).

        Args:
            file_path: Path to PDF file

        Returns:
            Extracted text or None if no text found
        """
        try:
            doc = fitz.open(file_path)
            text_parts = []

            for page_num in range(min(len(doc), 5)):  # Process up to 5 pages
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)

            doc.close()

            full_text = "\n\n".join(text_parts)

            # Return None if text is too short (probably an image-based PDF)
            if len(full_text.strip()) < 50:
                return None

            return full_text

        except Exception as e:
            logger.warning(f"Direct PDF text extraction failed: {e}")
            return None

    def _pdf_to_image(self, file_path: Path) -> Image.Image:
        """Convert first page of PDF to image.

        Args:
            file_path: Path to PDF file

        Returns:
            PIL Image of the first page
        """
        try:
            doc = fitz.open(file_path)
            page = doc[0]  # First page

            # Render page to image
            mat = fitz.Matrix(2, 2)  # 2x zoom for better OCR
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()

            return img
        except Exception as e:
            logger.error(f"Failed to convert PDF to image: {e}")
            raise OCRProcessingError(f"Failed to process PDF: {e}")

    def _process_extracted_text(self, text: str) -> OCRResult:
        """Process already-extracted text into OCRResult format.

        Args:
            text: Extracted text (from PDF or OCR)

        Returns:
            OCRResult with structured data
        """
        # Detect code blocks
        has_code = self._detect_code_blocks(text)

        # Segment into questions
        question_segments = self._segment_questions(text)

        # Create question objects
        questions = []
        total_confidence = 0.0

        for order, q_text, confidence in question_segments:
            requires_review = confidence < CONFIDENCE_MEDIUM
            questions.append(
                ExtractedQuestion(
                    order=order,
                    text=q_text,
                    confidence=confidence,
                    requires_review=requires_review,
                )
            )
            total_confidence += confidence

        avg_confidence = total_confidence / len(questions) if questions else 0.0

        logger.info(
            f"Extracted {len(questions)} questions "
            f"with avg confidence {avg_confidence:.1f}%"
        )

        return OCRResult(
            full_text=text,
            questions=questions,
            has_code=has_code,
            average_confidence=avg_confidence,
        )

    async def extract_from_path(self, file_path: Path) -> OCRResult:
        """Extract text from image or PDF file path.

        For PDFs: tries direct text extraction first, falls back to OCR if needed.
        For images: uses OCR directly.

        Args:
            file_path: Path to image or PDF file

        Returns:
            OCRResult with extracted text
        """
        # Check if file is PDF
        if file_path.suffix.lower() == ".pdf":
            # Try direct text extraction first
            direct_text = self._extract_text_from_pdf_direct(file_path)

            if direct_text:
                logger.info("PDF has embedded text, using direct extraction")
                return self._process_extracted_text(direct_text)
            else:
                logger.info("PDF appears to be image-based, using OCR")
                image = self._pdf_to_image(file_path)
                return await self.extract_from_image(image)

        # Regular image file
        with open(file_path, "rb") as f:
            return await self.extract_text(f)

    async def extract_from_image(self, image: Image.Image, preprocess: bool = True) -> OCRResult:
        """Extract text from PIL Image using OCR.

        Args:
            image: PIL Image object
            preprocess: Whether to apply image preprocessing

        Returns:
            OCRResult with extracted text
        """
        try:
            # Preprocess if enabled
            if preprocess:
                image = self._preprocess_image(image)

            # Perform OCR
            custom_config = r"--oem 3 --psm 6 -l " + self.lang
            full_text = pytesseract.image_to_string(image, config=custom_config)

            if not full_text.strip():
                raise OCRProcessingError(
                    "No text extracted from image. Image may be blank or unreadable."
                )

            return self._process_extracted_text(full_text)

        except OCRProcessingError:
            raise
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            raise OCRProcessingError(f"Failed to extract text: {str(e)}")

    async def extract_text(self, file_data: BinaryIO, preprocess: bool = True) -> OCRResult:
        """Extract text from image file data (backward-compatible shim).

        Args:
            file_data: Binary file data
            preprocess: Whether to apply image preprocessing

        Returns:
            OCRResult with extracted text and questions

        Raises:
            OCRProcessingError: If extraction fails
        """
        try:
            # Load image
            image = Image.open(file_data)

            # Process the image
            return await self.extract_from_image(image, preprocess)

        except OCRProcessingError:
            raise
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            raise OCRProcessingError(f"Failed to extract text: {str(e)}")

    def get_confidence_level(self, confidence: float) -> str:
        """Get confidence level description.

        Args:
            confidence: Confidence score (0-100)

        Returns:
            Level description: "high", "medium", or "low"
        """
        if confidence >= CONFIDENCE_HIGH:
            return "high"
        elif confidence >= CONFIDENCE_MEDIUM:
            return "medium"
        else:
            return "low"
