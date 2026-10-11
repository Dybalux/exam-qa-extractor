"""Pydantic schemas for the SPA-facing (``/api/v1/ui``) endpoints."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import PracticeMode
from app.schemas.analytics import (
    ExamCoverage,
    OverallStats,
    PartialProgress,
    SessionHistoryItem,
    TopicProgress,
    WeakArea,
)
from app.schemas.practice import SessionResults


class ExamSummary(BaseModel):
    """Minimal exam info for lists and selectors."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    partial_number: int
    exam_date: date | None = None
    topic_tags: str | None = None


class DashboardProgress(BaseModel):
    """Content readiness by partial and topic."""

    by_partial: dict[int, PartialProgress]
    by_topic: dict[str, TopicProgress]


class DashboardResponse(BaseModel):
    """Everything the dashboard screen needs in one request."""

    stats: OverallStats
    progress: DashboardProgress
    exams: list[ExamSummary]
    history: list[SessionHistoryItem]


class TopicOption(BaseModel):
    slug: str
    name: str


class PracticeOptionsResponse(BaseModel):
    """Choices available on the practice start screen."""

    modes: list[str]
    exams: list[ExamSummary]
    topics: list[TopicOption]


class PracticeSessionCreate(BaseModel):
    """Payload to start a practice session (user id comes from the cookie)."""

    mode: str = Field(default=PracticeMode.RANDOM.value)
    exam_id: int | None = None
    topic: str | None = None
    total_questions: int = Field(default=10, ge=1, le=100)


class SessionProgress(BaseModel):
    """Counters for a running session."""

    session_id: int
    mode: str
    total_questions: int
    questions_answered: int
    correct_count: int
    incorrect_count: int
    skipped_count: int
    is_completed: bool


class PracticeAnswerOption(BaseModel):
    """An answer choice. Never reveals whether it is correct."""

    id: int
    text: str


class PracticeQuestion(BaseModel):
    id: int
    text: str
    topic: str
    answers: list[PracticeAnswerOption]


class CurrentQuestionResponse(BaseModel):
    """Next unanswered question, or ``question=None`` when the session is done."""

    session: SessionProgress
    question: PracticeQuestion | None


class SubmitAnswerRequest(BaseModel):
    question_id: int
    selected_answer_id: int
    time_spent_seconds: int = Field(default=0, ge=0)


class SkipQuestionRequest(BaseModel):
    question_id: int
    time_spent_seconds: int = Field(default=0, ge=0)


class AnswerFeedback(BaseModel):
    """Instant feedback after submitting an answer."""

    is_correct: bool
    correct_answer_id: int | None
    correct_answer_text: str | None
    explanation: str | None
    session: SessionProgress


class SkipResponse(BaseModel):
    session: SessionProgress


class PracticeResultsResponse(SessionResults):
    """Results screen payload (same shape as the core results schema)."""


# ── Exams ────────────────────────────────────────────────────


class ExamListItem(ExamSummary):
    """Exam row with its question count."""

    question_count: int = 0


class ExamInput(BaseModel):
    """Payload to create or edit an exam."""

    partial_number: int = Field(ge=1, le=4)
    exam_date: date | None = None
    topic_tags: str | None = None


class QuestionRow(BaseModel):
    """Question row for lists and tables."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int
    question_text: str
    topic: str
    order_in_exam: int | None = None
    confidence_score: float | None = None
    is_corrected: bool
    is_ready_for_practice: bool


class ExamDetailResponse(BaseModel):
    """Exam detail with coverage and its questions."""

    exam: ExamListItem
    coverage: ExamCoverage
    questions: list[QuestionRow]


class UploadResult(BaseModel):
    """Outcome of an OCR upload."""

    created: int
    needing_review: int
    message: str


# ── Questions ────────────────────────────────────────────────


class QuestionListResponse(BaseModel):
    """Filtered question list plus the filter choices."""

    questions: list[QuestionRow]
    exams: list[ExamSummary]
    topics: list[TopicOption]


class ReviewQueueResponse(BaseModel):
    """Questions pending OCR review plus the exam filter choices."""

    questions: list[QuestionRow]
    exams: list[ExamSummary]


class AnswerRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    answer_text: str
    answer_type: str
    is_correct: bool
    is_common_misconception: bool
    explanation: str | None = None


class QuestionDetailResponse(BaseModel):
    question: QuestionRow
    extracted_text: str | None = None
    correction_notes: str | None = None
    answers: list[AnswerRow]


class ManualQuestionCreate(BaseModel):
    """Payload to add a question and its correct answer by hand."""

    question_text: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    order_in_exam: int | None = Field(default=None, ge=1)
    correct_answer_text: str = Field(min_length=1)
    explanation: str | None = None


class QuestionCreated(BaseModel):
    id: int


class CorrectionInput(BaseModel):
    corrected_text: str = Field(min_length=1)
    notes: str | None = None


# ── Analytics ────────────────────────────────────────────────


class TopicAccuracy(BaseModel):
    """The user's accuracy in one topic."""

    correct: int
    total: int
    accuracy_pct: float


class AnalyticsResponse(BaseModel):
    stats: OverallStats
    progress: DashboardProgress
    performance: dict[str, TopicAccuracy]


class WeakAreasResponse(BaseModel):
    threshold: float
    weak_areas: list[WeakArea]
    history: list[SessionHistoryItem]


class AnswerInput(BaseModel):
    """Payload to create or edit an answer."""

    answer_text: str = Field(min_length=1)
    answer_type: str = Field(default="incorrect")
    explanation: str | None = None
    is_common_misconception: bool = False


class AnswerOrder(BaseModel):
    """Answer IDs in the desired display order."""

    ordered_ids: list[int] = Field(min_length=1)
