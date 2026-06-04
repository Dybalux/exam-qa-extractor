"""Pydantic schemas for Exam resources."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ExamCreate(BaseModel):
    """Payload to create a new exam."""

    partial_number: int = Field(..., ge=1, le=4, description="Partial number (1-4)")
    exam_date: date | None = Field(None, description="Date of the exam")
    topic_tags: str | None = Field(None, description="Comma-separated topic tags")


class ExamUpdate(BaseModel):
    """Payload to update exam metadata."""

    exam_date: date | None = None
    topic_tags: str | None = None


class TagsUpdate(BaseModel):
    """Payload to add or remove topic tags."""

    tags: list[str] = Field(..., min_length=1)


class ExamResponse(BaseModel):
    """Full exam representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: str
    partial_number: int
    exam_date: date | None
    topic_tags: str | None
    created_at: datetime
    updated_at: datetime


class ExamStats(BaseModel):
    """Exam statistics summary."""

    exam_id: int
    partial_number: int
    exam_date: date | None
    topic_tags: str | None
    total_questions: int
    questions_by_topic: dict[str, int]
    ready_for_practice: int
    needs_answers: int
