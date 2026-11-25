"""Domain constants and enums for the exam study system."""

from enum import Enum


# DEPRECATED — Use the dynamic Topic database table instead.
# Kept for backward compatibility with legacy code that may still
# reference the enum values.  New code MUST resolve topics via the
# Topic model in ``app.models.topic``.
class TopicEnum(str, Enum):
    """Operating Systems topics for question classification."""

    PROCESSES = "processes"
    MEMORY = "memory"
    FILES = "files"
    SCHEDULING = "scheduling"
    DEADLOCK = "deadlock"
    SYNCHRONIZATION = "synchronization"
    IO = "io"
    SECURITY = "security"
    OTHER = "other"


class AnswerType(str, Enum):
    """Types of answers for questions."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    PARTIAL = "partial"


class PracticeMode(str, Enum):
    """Practice session modes."""

    RANDOM = "random"
    BY_PARTIAL = "by_partial"
    BY_TOPIC = "by_topic"
    EXAM_SIMULATION = "exam_simulation"
    ERROR_REVIEW = "error_review"


class OCRStatus(str, Enum):
    """OCR processing status for exam images."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Valid partial numbers for exams
VALID_PARTIAL_NUMBERS = [1, 2, 3, 4]

# Difficulty scale
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5

# File upload constants
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": [b"\xff\xd8\xff"],  # JPEG
    "image/png": [b"\x89PNG\r\n\x1a\n"],  # PNG
    "image/gif": [b"GIF87a", b"GIF89a"],  # GIF
    "application/pdf": [b"%PDF"],  # PDF
}

MAX_FILE_SIZE_MB = 10

# OCR confidence thresholds
CONFIDENCE_HIGH = 80.0
CONFIDENCE_MEDIUM = 60.0
CONFIDENCE_LOW = 40.0

# Topic distribution blueprints for exam simulations by partial number.
# Maps partial_number -> {topic_slug: target_percentage}
EXAM_SIMULATION_BLUEPRINTS: dict[int, dict[str, float]] = {
    3: {
        "processes": 0.10,  # Cap. 4: Hilos / Multithreading / Procesos (10%)
        "scheduling": 0.30,  # Cap. 5: Planificación de CPU (30%)
        "synchronization": 0.30,  # Cap. 6: Sincronización de Procesos (30%)
        "deadlock": 0.20,  # Cap. 7: Deadlocks / Abrazo Mortal (20%)
        "memory": 0.10,  # Cap. 8: Gestión de Memoria Principal (10%)
    },
    4: {
        "memory": 0.25,  # Cap. 9 + TP MV: Memoria Virtual y Swap (25%)
        "files": 0.45,  # Caps. 10-11 + TP SA: Sistemas de Archivos (45%)
        "io": 0.30,  # Caps. 12-13 + TP E/S: Almacenamiento Masivo y E/S (30%)
    },
}
