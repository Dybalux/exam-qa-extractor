"""Pydantic schemas for Exam resources."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ExamCreate(BaseModel):
    """Payload to create a new exam."""

    partial_number: int = Field(..., ge=1, le=4, description="Partial number (1-4)")
    exam_date: date | None = Field(None, description="Date of the exam")
    topic_tags: str | None = Field(None, description="Comma-separated topic tags")
    subject_id: int | None = Field(
        None, description="Subject ID. Defaults to 'sistemas-operativos'."
    )


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
