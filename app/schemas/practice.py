"""Pydantic schemas for Practice Session resources."""

from pydantic import BaseModel


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
