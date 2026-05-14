"""Pydantic schemas for Analytics resources."""

from pydantic import BaseModel


class OverallStats(BaseModel):
    """System-wide statistics."""

    total_exams: int
    total_questions: int
    questions_ready_for_practice: int
    questions_corrected: int
    practice_readiness_pct: float
    total_practice_sessions: int
    completed_practice_sessions: int


class TopicPerformanceItem(BaseModel):
    """Accuracy stats for a single topic."""

    topic: str
    correct: int
    total: int
    accuracy_pct: float


class WeakArea(BaseModel):
    """Topic where the user performs below threshold."""

    topic: str
    correct: int
    total: int
    accuracy_pct: float


class SessionHistoryItem(BaseModel):
    """Summary of a single past practice session."""

    session_id: int
    mode: str
    is_completed: bool
    total_questions: int
    questions_answered: int
    correct_count: int
    accuracy_pct: float
    total_time_seconds: int | None
    started_at: str
    completed_at: str | None


class PartialProgress(BaseModel):
    """Readiness stats for a single partial."""

    total: int
    ready: int
    readiness_pct: float


class TopicProgress(BaseModel):
    """Readiness stats for a single topic."""

    total: int
    ready: int
    readiness_pct: float


class StudyProgress(BaseModel):
    """Content readiness broken down by partial and topic."""

    by_partial: dict[str, PartialProgress]
    by_topic: dict[str, TopicProgress]


class TopicCoverage(BaseModel):
    """Per-topic coverage within an exam."""

    total: int
    ready: int
    corrected: int
    readiness_pct: float


class ExamCoverage(BaseModel):
    """Exam-level readiness breakdown."""

    exam_id: int
    total_questions: int
    ready_for_practice: int
    corrected: int
    readiness_pct: float
    correction_pct: float
    by_topic: dict[str, TopicCoverage]
