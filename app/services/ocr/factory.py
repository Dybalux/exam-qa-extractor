"""OCR Provider Factory with singleton pattern and fallback logic."""

import logging
from typing import Optional

from app.config import get_settings
from app.core.exceptions import OCRProcessingError
from app.services.ocr.base import BaseOCRProvider
from app.services.ocr.openai_vision import OpenAIVisionProvider
from app.services.ocr.tesseract import TesseractProvider

logger = logging.getLogger(__name__)


class OCRProviderFactory:
    """Factory class that provides singleton access to OCR providers with fallback logic.
    
    This factory manages the instantiation and caching of OCR providers, supporting
    runtime fallback from OpenAI Vision to Tesseract in case of initialization failures.
    """

    _provider: Optional[BaseOCRProvider] = None

    @classmethod
    def get_provider(cls, name: Optional[str] = None) -> BaseOCRProvider:
        """Get or create the OCR provider instance.
        
        Args:
            name: Provider name ("tesseract" or "openai"). If None, uses config.ocr_provider.
        
        Returns:
            Configured OCR provider instance.
        
        Raises:
            ValueError: If an unknown provider name is specified.
        """
        if cls._provider is not None:
            return cls._provider

        # Resolve provider name from config if not specified
        if name is None:
            settings = get_settings()
            name = settings.ocr_provider

        logger.info(f"Initializing OCR provider: {name}")

        # Create provider based on name
        try:
            if name == "tesseract":
                cls._provider = TesseractProvider()
            elif name == "openai":
                provider = OpenAIVisionProvider()
                
                # VALIDACIÓN REAL: Validamos la salud del proveedor antes de darlo por inicializado
                health = provider.health_check()
                if health["status"] != "ok":
                    raise OCRProcessingError(
                        f"OpenAI provider is unhealthy: {health.get('error')}"
                    )
                
                cls._provider = provider
            else:
                raise ValueError(f"Unknown OCR provider: {name}")

            logger.info(f"OCR provider '{name}' initialized successfully")
            return cls._provider

        except Exception as e:
            # Fallback logic: if OpenAI fails, fall back to Tesseract
            if name == "openai":
                logger.warning(
                    f"OpenAI provider initialization failed ({e}), falling back to Tesseract"
                )
                try:
                    cls._provider = TesseractProvider()
                    logger.info("Fallback to Tesseract provider successful")
                    return cls._provider
                except Exception as fallback_error:
                    logger.error(
                        f"Fallback to Tesseract also failed: {fallback_error}"
                    )
                    raise OCRProcessingError(
                        f"Both OpenAI and Tesseract providers failed to initialize. "
                        f"Original error: {e}, Fallback error: {fallback_error}"
                    ) from fallback_error
            else:
                # For Tesseract or unknown providers, just raise the error
                logger.error(f"Provider initialization failed: {e}")
                raise


def get_ocr_provider() -> BaseOCRProvider:
    """Get the configured OCR provider instance.
    
    Convenience function that returns the singleton provider instance.
    
    Returns:
        Configured OCR provider instance.
    """
    return OCRProviderFactory.get_provider()
