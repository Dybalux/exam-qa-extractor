"""File Storage Service for secure file upload handling."""

import logging
import magic
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from app.config import get_settings
from app.core.constants import ALLOWED_IMAGE_TYPES, MAX_FILE_SIZE_MB
from app.core.exceptions import FileValidationError, StorageError

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class FileUploadResult:
    """Result of a file upload operation."""

    filename: str
    original_name: str
    storage_path: Path
    mime_type: str
    size_bytes: int


class StorageService:
    """Service for secure file storage operations."""

    def __init__(
        self,
        upload_dir: Path | None = None,
        max_size: int | None = None,
    ):
        """Initialize storage service.
        
        Args:
            upload_dir: Base upload directory (uses settings if not provided)
            max_size: Maximum file size in bytes (uses settings if not provided)
        """
        self.upload_dir = upload_dir or settings.upload_path
        self.max_size = max_size or settings.max_upload_size
        self._ensure_upload_dir()

    def _ensure_upload_dir(self) -> None:
        """Create upload directory if it doesn't exist."""
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _validate_file_type(self, file_data: BinaryIO) -> str:
        """Validate file type using magic numbers.
        
        Args:
            file_data: Binary file data
            
        Returns:
            Detected MIME type
            
        Raises:
            FileValidationError: If file type is invalid
        """
        # Read magic bytes
        file_data.seek(0)
        magic_bytes = file_data.read(2048)
        file_data.seek(0)
        
        # Detect MIME type
        try:
            mime = magic.from_buffer(magic_bytes, mime=True)
        except Exception as e:
            logger.error(f"Magic detection failed: {e}")
            raise FileValidationError(f"Could not determine file type: {e}")
        
        # Validate against allowed types
        if mime not in ALLOWED_IMAGE_TYPES:
            raise FileValidationError(
                f"Invalid file type: {mime}. Allowed types: {', '.join(ALLOWED_IMAGE_TYPES.keys())}"
            )
        
        return mime

    def _validate_file_size(self, file_data: BinaryIO) -> int:
        """Validate file size.
        
        Args:
            file_data: Binary file data
            
        Returns:
            File size in bytes
            
        Raises:
            FileValidationError: If file is too large
        """
        file_data.seek(0, 2)  # Seek to end
        size = file_data.tell()
        file_data.seek(0)
        
        if size > self.max_size:
            max_mb = self.max_size / (1024 * 1024)
            actual_mb = size / (1024 * 1024)
            raise FileValidationError(
                f"File too large: {actual_mb:.1f}MB (max: {max_mb:.1f}MB)"
            )
        
        if size == 0:
            raise FileValidationError("File is empty")
        
        return size

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize and secure filename.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove path components
        filename = Path(filename).name
        
        # Remove null bytes
        filename = filename.replace("\x00", "")
        
        # Limit length
        if len(filename) > 255:
            name, ext = Path(filename).stem, Path(filename).suffix
            filename = name[:250] + ext
        
        return filename

    def _generate_storage_path(
        self,
        exam_id: int | None = None,
        extension: str = ".jpg",
    ) -> Path:
        """Generate organized storage path.
        
        Args:
            exam_id: Optional exam ID for organization
            extension: File extension
            
        Returns:
            Path for file storage
        """
        now = datetime.now()
        
        # Create directory structure: uploads/YYYY/MM/ or uploads/exam_{id}/
        if exam_id:
            subdir = self.upload_dir / f"exam_{exam_id}"
        else:
            subdir = self.upload_dir / str(now.year) / f"{now.month:02d}"
        
        subdir.mkdir(parents=True, exist_ok=True)
        
        # Generate UUID filename
        filename = f"{uuid.uuid4().hex}{extension}"
        return subdir / filename

    def _get_extension_from_mime(self, mime_type: str) -> str:
        """Get file extension from MIME type.
        
        Args:
            mime_type: MIME type
            
        Returns:
            File extension
        """
        extensions = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "application/pdf": ".pdf",
        }
        return extensions.get(mime_type, ".bin")

    async def save_file(
        self,
        file_data: BinaryIO,
        original_filename: str,
        exam_id: int | None = None,
    ) -> FileUploadResult:
        """Save uploaded file securely.
        
        Args:
            file_data: Binary file data
            original_filename: Original filename for reference
            exam_id: Optional exam ID for organization
            
        Returns:
            FileUploadResult with storage details
            
        Raises:
            FileValidationError: If validation fails
            StorageError: If storage operation fails
        """
        try:
            # Validate
            mime_type = self._validate_file_type(file_data)
            size = self._validate_file_size(file_data)
            
            # Sanitize filename
            safe_name = self._sanitize_filename(original_filename)
            
            # Generate storage path
            extension = self._get_extension_from_mime(mime_type)
            storage_path = self._generate_storage_path(exam_id, extension)
            
            # Save file
            try:
                with open(storage_path, "wb") as f:
                    shutil.copyfileobj(file_data, f)
            except Exception as e:
                logger.error(f"Failed to save file: {e}")
                raise StorageError(f"Failed to save file: {e}")
            
            logger.info(f"Saved file: {storage_path} ({size} bytes)")
            
            return FileUploadResult(
                filename=storage_path.name,
                original_name=safe_name,
                storage_path=storage_path,
                mime_type=mime_type,
                size_bytes=size,
            )
            
        except (FileValidationError, StorageError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving file: {e}")
            raise StorageError(f"Failed to save file: {e}")

    async def delete_file(self, file_path: Path) -> bool:
        """Delete a stored file.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if deleted, False if not found
        """
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted file: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            raise StorageError(f"Failed to delete file: {e}")

    def get_file_url(self, file_path: Path) -> str:
        """Get URL for a stored file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Relative URL for file
        """
        # Return path relative to upload_dir
        try:
            return str(file_path.relative_to(self.upload_dir))
        except ValueError:
            return str(file_path)

    def validate_upload(
        self,
        file_data: BinaryIO,
        original_filename: str,
    ) -> tuple[bool, str]:
        """Validate upload without saving.
        
        Args:
            file_data: Binary file data
            original_filename: Original filename
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            self._validate_file_type(file_data)
            self._validate_file_size(file_data)
            self._sanitize_filename(original_filename)
            return True, ""
        except FileValidationError as e:
            return False, str(e.message)
        except Exception as e:
            return False, str(e)
