"""Custom domain exceptions for the exam study system."""


class ExamStudyError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class OCRProcessingError(ExamStudyError):
    """Raised when OCR processing fails."""

    pass


class FileValidationError(ExamStudyError):
    """Raised when file upload validation fails."""

    pass


class StorageError(ExamStudyError):
    """Raised when file storage operations fail."""

    pass


class NotFoundError(ExamStudyError):
    """Raised when a requested resource is not found."""

    pass


class ValidationError(ExamStudyError):
    """Raised when data validation fails."""

    pass


class ConflictError(ExamStudyError):
    """Raised when there's a conflict with existing data."""

    pass
