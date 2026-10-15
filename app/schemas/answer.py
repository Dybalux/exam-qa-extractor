"""Pydantic schemas for Answer resources."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AnswerResponse(BaseModel):
    """Full answer representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: str
    question_id: int
    answer_text: str
    answer_type: str
    is_correct: bool
    is_common_misconception: bool
    explanation: str | None
    display_order: int
    created_at: datetime
    updated_at: datetime
