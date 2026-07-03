"""PracticeSession model for tracking practice sessions."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import PracticeMode
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.exam import Exam
    from app.models.practice_response import PracticeResponse


class PracticeSession(Base):
    """PracticeSession model for tracking study sessions."""

    __tablename__ = "practice_sessions"

    __table_args__ = (
        CheckConstraint(
            "mode IN ('random', 'by_partial', 'by_topic', 'exam_simulation', 'error_review')",
            name="check_valid_practice_mode",
        ),
        Index("idx_session_user", "user_session_id"),
        Index("idx_session_exam", "exam_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_session_id: Mapped[str] = mapped_column(String(100), nullable=False)
    mode: Mapped[str] = mapped_column(
        String(30),
        default=PracticeMode.RANDOM.value,
        nullable=False,
    )
    exam_id: Mapped[int | None] = mapped_column(
        ForeignKey("exams.id", ondelete="SET NULL"),
        nullable=True,
    )
    filters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    total_questions: Mapped[int] = mapped_column(default=10, nullable=False)
    questions_answered: Mapped[int] = mapped_column(default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(default=0, nullable=False)
    incorrect_count: Mapped[int] = mapped_column(default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    total_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    exam: Mapped["Exam | None"] = relationship(back_populates="practice_sessions")
    responses: Mapped[list["PracticeResponse"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<PracticeSession(id={self.id}, mode={self.mode}, user={self.user_session_id[:8]}...)>"

    @property
    def is_completed(self) -> bool:
        """Check if session is completed."""
        return self.completed_at is not None

    @property
    def accuracy(self) -> float:
        """Calculate accuracy percentage."""
        if self.questions_answered == 0:
            return 0.0
        return (self.correct_count / self.questions_answered) * 100
