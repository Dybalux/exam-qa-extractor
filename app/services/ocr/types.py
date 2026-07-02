"""Dataclasses for OCR extraction results."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ExtractedAnswer:
    """Represents an extracted answer option with classification."""

    text: str
    answer_type: Literal["correct", "incorrect", "partial"]
    explanation: str | None = None
    display_order: int = 0


@dataclass
class ExtractedQuestion:
    """Represents an extracted question with metadata."""

    order: int
    text: str
    confidence: float = 0.0
    requires_review: bool = False
    answers: list[ExtractedAnswer] = field(default_factory=list)


@dataclass
class OCRResult:
    """Result of OCR processing."""

    full_text: str
    questions: list[ExtractedQuestion] = field(default_factory=list)
    has_code: bool = False
    average_confidence: float = 0.0
