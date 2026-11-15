"""Pydantic schemas for Exam resources."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


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
