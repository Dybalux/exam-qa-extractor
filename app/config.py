"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "sqlite+aiosqlite:///./database.db"

    # File uploads
    upload_dir: str = "./uploads"
    max_upload_size: int = 10 * 1024 * 1024  # 10MB

    # Import (JSON metadata backup/restore). Distinct from `max_upload_size`
    # because the two domains may diverge in the future (e.g. raising image
    # upload to 50 MB without raising the JSON import cap).
    max_import_size_mb: int = 10

    # OCR
    ocr_provider: str = "tesseract"
    tesseract_cmd: str = "tesseract"
    tesseract_lang: str = "spa"
    openai_api_key: str | None = None
    openai_vision_model: str = "gpt-4o-mini"
    openai_max_image_size_mb: int = 4

    # App
    debug: bool = False
    secret_key: str = "change-this-secret-key-in-production"

    # CORS — override via env vars in production
    cors_allowed_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]
    cors_allow_credentials: bool = True
    cors_allowed_methods: list[str] = ["GET", "POST", "PATCH", "DELETE"]
    cors_allowed_headers: list[str] = ["Authorization", "Content-Type"]

    @property
    def upload_path(self) -> Path:
        """Get upload directory as Path object."""
        return Path(self.upload_dir)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
