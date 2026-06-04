"""Pydantic schemas for Answer resources."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import AnswerType


class AnswerCreate(BaseModel):
    """Payload to create a new answer."""

    question_id: int
    answer_text: str = Field(..., min_length=1)
    answer_type: str = Field(default=AnswerType.INCORRECT.value)
    explanation: str | None = None
    is_common_misconception: bool = False
    display_order: int = Field(default=0, ge=0)


class AnswerUpdate(BaseModel):
    """Payload to update an answer."""

    answer_text: str | None = Field(None, min_length=1)
    answer_type: str | None = None
    explanation: str | None = None
    is_common_misconception: bool | None = None
    display_order: int | None = Field(None, ge=0)


class ReorderRequest(BaseModel):
    """Payload to reorder answers for a question."""

    ordered_ids: list[int] = Field(..., min_length=1)


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
