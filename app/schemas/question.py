"""Pydantic schemas for Question resources."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import TopicEnum


class QuestionCreate(BaseModel):
    """Payload to create a question manually."""

    exam_id: int
    question_text: str = Field(..., min_length=1)
    topic: str = Field(default=TopicEnum.OTHER.value)
    order_in_exam: int | None = Field(None, ge=1, le=50)
    difficulty: int = Field(default=3, ge=1, le=5)
    image_id: int | None = None
    extracted_text: str | None = None
    confidence_score: float | None = Field(None, ge=0.0, le=100.0)


class QuestionUpdate(BaseModel):
    """Payload to update a question."""

    question_text: str | None = Field(None, min_length=1)
    topic: str | None = None
    difficulty: int | None = Field(None, ge=1, le=5)
    order_in_exam: int | None = Field(None, ge=1, le=50)
    correction_notes: str | None = None
    is_corrected: bool | None = None
    has_code_in_answers: bool | None = None


class OCRCorrection(BaseModel):
    """Payload to submit a manual OCR correction."""

    corrected_text: str = Field(..., min_length=1)
    notes: str | None = None


class BulkQuestionItem(BaseModel):
    """Single question entry for bulk OCR import."""

    question_text: str = Field(..., min_length=1)
    extracted_text: str | None = None
    confidence_score: float | None = Field(None, ge=0.0, le=100.0)
    topic: str = TopicEnum.OTHER.value
    order_in_exam: int | None = None
    difficulty: int = Field(default=3, ge=1, le=5)


class BulkCreateRequest(BaseModel):
    """Payload for bulk question creation from OCR results."""

    exam_id: int
    image_id: int | None = None
    questions: list[BulkQuestionItem] = Field(..., min_length=1)


class QuestionResponse(BaseModel):
    """Full question representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int
    image_id: int | None
    question_text: str
    extracted_text: str | None
    confidence_score: float | None
    topic: str
    order_in_exam: int | None
    is_corrected: bool
    correction_notes: str | None
    difficulty: int
    has_code_in_answers: bool
    is_ready_for_practice: bool
    created_at: datetime
    updated_at: datetime


class BulkCreateResponse(BaseModel):
    """Response for bulk question creation."""

    created: int
    questions: list[QuestionResponse]
