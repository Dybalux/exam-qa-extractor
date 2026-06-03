"""OpenAI Vision OCR provider implementation."""

import asyncio
import base64
import io
import json
import logging
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF for PDF support
import langfuse as langfuse_mod
from openai import OpenAI, RateLimitError
from langfuse.openai import AsyncOpenAI
from PIL import Image

from app.config import get_settings
from app.core.exceptions import OCRProcessingError
from app.services.ocr.base import BaseOCRProvider
from app.services.ocr.types import ExtractedAnswer, ExtractedQuestion, OCRResult

logger = logging.getLogger(__name__)

# --- Langfuse initialization (once per process, at import time) ---
_settings = get_settings()
_langfuse_client = None
if _settings.langfuse_public_key and _settings.langfuse_secret_key:
    _langfuse_client = langfuse_mod.Langfuse(
        public_key=_settings.langfuse_public_key,
        secret_key=_settings.langfuse_secret_key,
        host=_settings.langfuse_host,
    )
    logger.info(
        "Langfuse tracing enabled — host=%s  model=%s",
        _settings.langfuse_host,
        _settings.openai_vision_model,
    )
else:
    logger.info(
        "Langfuse not configured (missing LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY) "
        "— OpenAI calls will NOT be traced"
    )

OPENAI_JSON_SCHEMA = {
    "name": "ExamExtraction",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "full_text": {"type": "string"},
            "has_code": {"type": "boolean"},
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "order": {"type": "integer"},
                        "text": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 100},
                        "requires_review": {"type": "boolean"},
                        "answers": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string"},
                                    "answer_type": {
                                        "type": "string",
                                        "enum": ["correct", "incorrect", "partial"],
                                    },
                                    "explanation": {"type": "string"},
                                    "display_order": {"type": "integer"},
                                },
                                "required": [
                                    "text",
                                    "answer_type",
                                    "explanation",
                                    "display_order",
                                ],
                                "additionalProperties": False,
                             },
                        },
                    },
                    "required": [
                        "order",
                        "text",
                        "confidence",
                        "requires_review",
                        "answers",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["full_text", "has_code", "questions"],
        "additionalProperties": False,
    },
}

SYSTEM_PROMPT = """Eres un asistente especializado en extraer preguntas de exámenes universitarios a partir de imágenes.

Tu tarea CRÍTICA:
1. Extraer **TODAS** las preguntas del examen en orden numérico. NO omitas ninguna pregunta.
2. Para cada pregunta, extraer **TODAS** las opciones de respuesta (a, b, c, d, etc.).
3. Clasificar cada respuesta como "correct", "incorrect", o "partial" según el contenido del examen.
4. Si una respuesta es correcta, incluir una breve explicación de por qué es correcta. Si no hay explicación visible en el examen, dejar "explanation" como string vacío.
5. Asignar "display_order" según el orden de aparición (1=a, 2=b, 3=c, etc.).
6. Estimar la confianza de extracción (0-100) para cada pregunta.
7. Marcar "requires_review": true si la imagen es borrosa, hay texto ilegible, o la confianza es menor a 70.
8. Detectar si el examen contiene bloques de código o pseudocódigo y marcar "has_code": true.

IMPORTANTE:
- Si el examen tiene 10 preguntas, debes extraer EXACTAMENTE 10 preguntas. NO extraigas solo algunas.
- Revisa cuidadosamente toda la imagen, incluyendo márgenes y columnas laterales.
- Las preguntas pueden estar numeradas como "1.", "1)", "Pregunta 1", etc.
- Si una pregunta está parcialmente cortada en el borde de la imagen, igual intentá extraerla y marcá "requires_review": true.

El examen está en español. Mantener el texto original de las preguntas y respuestas en español.

Si no hay opciones de respuesta visibles para una pregunta, dejar "answers" como lista vacía [].

Responder ÚNICAMENTE con el JSON solicitado. No incluir texto adicional."""


class OpenAIVisionProvider(BaseOCRProvider):
    """OCR provider using OpenAI Vision API for exam extraction."""

    def __init__(self) -> None:
        """Initialize the OpenAI Vision provider."""
        self._settings = get_settings()
        # Cliente asíncrono para la extracción en runtime
        self._client = AsyncOpenAI(api_key=self._settings.openai_api_key)
        # Cliente síncrono exclusivo para el health_check() libre de colisiones de event loop
        self._sync_client = OpenAI(api_key=self._settings.openai_api_key)

    @property
    def engine_name(self) -> str:
        """Return the provider's identifier string."""
        return "openai"

    async def extract_from_path(self, file_path: Path) -> OCRResult:
        """Extract text/structure from a file on disk.

        Args:
            file_path: Path to image or PDF file.

        Returns:
            OCRResult with extracted text and structured questions.
        """
        try:
            # Check if file is PDF - convert to image first
            if file_path.suffix.lower() == ".pdf":
                logger.info(f"PDF detected, converting to image: {file_path}")
                image = self._pdf_to_image(file_path)
            else:
                image = Image.open(file_path)
            
            return await self.extract_from_image(image)
        except Exception as e:
            logger.error(f"Failed to open file from path {file_path}: {e}")
            raise OCRProcessingError(f"Failed to read file: {str(e)}")

    async def extract_from_image(self, image: Image.Image) -> OCRResult:
        """Extract text/structure from a PIL Image object.

        Args:
            image: PIL Image object.

        Returns:
            OCRResult with extracted text and structured questions.
        """
        return await self._process_image(image)

    def health_check(self) -> dict:
        """Return provider health status using a safe synchronous connection.

        Returns:
            Dict with health information.
        """
        if not self._settings.openai_api_key:
            return {
                "status": "error",
                "engine": self.engine_name,
                "error": "OpenAI API key is not configured.",
            }

        try:
            # Una llamada de autenticación mínima de 1 token para verificar la key sin romper el loop de FastAPI
            self._sync_client.chat.completions.create(
                model=self._settings.openai_vision_model,
                messages=[{"role": "user", "content": "OK"}],
                max_tokens=1,
                timeout=5.0,
            )
            return {"status": "ok", "engine": self.engine_name}
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            return {"status": "error", "engine": self.engine_name, "error": str(e)}

    def _pdf_to_image(self, file_path: Path) -> Image.Image:
        """Convert first page of PDF to image.

        Args:
            file_path: Path to PDF file.

        Returns:
            PIL Image of the first page.
        """
        try:
            doc = fitz.open(file_path)
            page = page = doc[0]  # First page only
            
            # Render at 2x zoom for better OCR quality
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            doc.close()
            logger.info(f"PDF converted to image: {pix.width}x{pix.height}")
            return image
            
        except Exception as e:
            logger.error(f"Failed to convert PDF to image: {e}")
            raise OCRProcessingError(f"Failed to process PDF: {e}")

    async def _process_image(self, image: Image.Image) -> OCRResult:
        """Process an image and return OCR results.

        Args:
            image: PIL Image to process.

        Returns:
            OCRResult with extracted data.
        """
        if not self._settings.openai_api_key:
            raise OCRProcessingError("OpenAI API key is missing. Please configure OPENAI_API_KEY.")

        max_size_mb = self._settings.openai_max_image_size_mb
        max_size_bytes = max_size_mb * 1024 * 1024

        # Resize image if necessary
        image_buffer = self._resize_image(image, max_size_bytes)

        # Convert to base64
        image_buffer.seek(0)
        base64_image = base64.b64encode(image_buffer.read()).decode("utf-8")

        # Retry logic with exponential backoff
        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                response = await self._client.chat.completions.create(
                    model=self._settings.openai_vision_model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Extract exam questions from this image:",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    },
                                },
                            ],
                        },
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": OPENAI_JSON_SCHEMA,
                    },
                    timeout=30.0,  # El timeout de la API de OpenAI se configura acá
                )

                content = response.choices[0].message.content
                if not content:
                    raise OCRProcessingError("Empty response from OpenAI API")

                return self._parse_response(content)

            except RateLimitError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.warning(f"OpenAI API 429 Rate Limit. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                raise OCRProcessingError("OpenAI API rate limit exceeded.") from e
            except Exception as e:
                logger.error(f"OpenAI completion failed: {e}")
                raise OCRProcessingError(f"OpenAI Vision extraction failed: {str(e)}") from e

        raise OCRProcessingError("Max retries exceeded for OpenAI API call")

    def _resize_image(self, image: Image.Image, max_size_bytes: int) -> io.BytesIO:
        """Resize image to fit within size limit.

        Args:
            image: PIL Image to resize.
            max_size_bytes: Maximum file size in bytes.

        Returns:
            BytesIO buffer with resized image.
        """
        buffer = io.BytesIO()

        # First, try reducing dimensions while maintaining aspect ratio
        width, height = image.size
        scale_factor = 1.0

        # Convert to RGB if necessary (JPEG doesn't support RGBA)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # Reduce dimensions if needed
        while scale_factor > 0.1:
            buffer.truncate(0)
            buffer.seek(0)

            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            resized.save(buffer, format="JPEG", quality=95)

            if buffer.tell() <= max_size_bytes:
                break

            scale_factor -= 0.1

        # If still too large, reduce JPEG quality
        quality = 95
        while quality >= 10:
            buffer.truncate(0)
            buffer.seek(0)

            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            resized.save(buffer, format="JPEG", quality=quality)

            if buffer.tell() <= max_size_bytes:
                break

            quality -= 5

        buffer.seek(0)
        return buffer

    def _parse_response(self, content: str) -> OCRResult:
        """Parse JSON response from OpenAI API.

        Args:
            content: JSON string from API response.

        Returns:
            OCRResult with parsed data.
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise OCRProcessingError(f"Invalid JSON response from OpenAI: {e}")

        try:
            questions = []
            total_confidence = 0.0

            for q_data in data.get("questions", []):
                answers = [
                    ExtractedAnswer(
                        text=a["text"],
                        answer_type=a["answer_type"],
                        explanation=a.get("explanation", ""),
                        display_order=a["display_order"],
                    )
                    for a in q_data.get("answers", [])
                ]

                question = ExtractedQuestion(
                    order=q_data["order"],
                    text=q_data["text"],
                    confidence=q_data["confidence"],
                    requires_review=q_data["requires_review"],
                    answers=answers,
                )
                questions.append(question)
                total_confidence += q_data["confidence"]

            avg_confidence = (
                total_confidence / len(questions) if questions else 0.0
            )

            return OCRResult(
                full_text=data["full_text"],
                questions=questions,
                has_code=data.get("has_code", False),
                average_confidence=avg_confidence,
            )
        except KeyError as e:
            logger.error(f"Failed to parse structured JSON. Missing key: {e}")
            raise OCRProcessingError(
                f"OpenAI JSON response structure mismatch. Missing expected key: {e}"
            )
