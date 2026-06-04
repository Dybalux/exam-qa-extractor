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


class MalformedImportError(ExamStudyError):
    """Raised when one or more import entries fail Pydantic validation.

    Per decision #113, malformed entries are NOT skipped: the service
    collects every failure and raises this exception, which the API
    layer maps to HTTP 400 with a body of the form
    ``{"detail": "Malformed import", "validation_errors": [...]}``.

    The ``details`` dict always carries a ``validation_errors`` key
    whose value is a list of ``{index, uuid, field_errors: [...]}``
    entries. The exact entry shape mirrors what
    :class:`~app.schemas.json_io.ImportPreviewSchema.validation_errors`
    uses, so the dry-run and the apply path report errors identically.
    """

    pass


class UnknownSchemaVersion(ExamStudyError):
    """Raised when the import JSON's ``schema_version`` is unsupported.

    The service supports a closed set declared on
    :class:`~app.services.json_io_service.JsonIOService.SUPPORTED_VERSIONS`.
    Any other value triggers this exception, which the API layer maps
    to HTTP 400.
    """

    pass


class PayloadTooLargeError(ExamStudyError):
    """Raised when the import JSON exceeds ``max_import_size_mb``.

    The API layer maps this to HTTP 413 Payload Too Large. The check
    fires before any JSON parse, so oversize payloads do not waste
    server resources on a doomed parse.
    """

    pass
