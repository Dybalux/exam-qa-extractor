"""Pydantic schemas for Question resources."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class QuestionResponse(BaseModel):
    """Full question representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: str
    exam_id: int
    image_id: int | None
    question_text: str
    extracted_text: str | None
    confidence_score: float | None
    topic: str
    order_in_exam: int | None
    is_corrected: bool
    correction_notes: str | None
    has_code_in_answers: bool
    is_ready_for_practice: bool
    created_at: datetime
    updated_at: datetime
