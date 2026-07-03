"""Pydantic schemas for Practice Session resources."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import PracticeMode


class SessionCreate(BaseModel):
    """Payload to start a new practice session."""

    user_session_id: str = Field(..., min_length=1, max_length=100)
    mode: str = Field(default=PracticeMode.RANDOM.value)
    exam_id: int | None = None
    filters: dict | None = Field(
        None,
        description="Optional filters: topic",
    )
    total_questions: int = Field(default=10, ge=1, le=100)


class SessionResponse(BaseModel):
    """Full practice session representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_session_id: str
    mode: str
    exam_id: int | None
    filters: dict | None
    total_questions: int
    questions_answered: int
    correct_count: int
    incorrect_count: int
    skipped_count: int
    is_completed: bool
    accuracy: float
    total_time_seconds: int | None
    started_at: datetime
    completed_at: datetime | None


class AnswerSubmission(BaseModel):
    """Payload to submit an answer."""

    question_id: int
    selected_answer_id: int
    time_spent_seconds: int = Field(default=0, ge=0)
    was_flagged: bool = False


class SkipRequest(BaseModel):
    """Payload to skip a question."""

    question_id: int
    time_spent_seconds: int = Field(default=0, ge=0)


class ResponseRecord(BaseModel):
    """Single question response record within session results."""

    question_id: int
    question_text: str | None = None
    selected_answer_id: int | None
    selected_answer_text: str | None = None
    is_correct: bool | None
    correct_answer_text: str | None = None
    explanation: str | None = None
    time_spent_seconds: int
    was_flagged: bool
    skipped: bool = False


class SessionResults(BaseModel):
    """Complete results for a practice session."""

    session_id: int
    mode: str
    is_completed: bool
    total_questions: int
    questions_answered: int
    correct_count: int
    incorrect_count: int
    skipped_count: int
    accuracy: float
    total_time_seconds: int | None
    responses: list[ResponseRecord]
