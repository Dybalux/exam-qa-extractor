"""PracticeResponse model for individual question responses."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.answer import Answer
    from app.models.practice_session import PracticeSession
    from app.models.question import Question


class PracticeResponse(Base):
    """PracticeResponse model for tracking answers to questions."""

    __tablename__ = "practice_responses"

    __table_args__ = (
        Index("idx_response_session", "session_id"),
        Index("idx_response_question", "question_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    selected_answer_id: Mapped[int | None] = mapped_column(
        ForeignKey("answers.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_correct: Mapped[bool | None] = mapped_column(nullable=True)
    time_spent_seconds: Mapped[int] = mapped_column(default=0, nullable=False)
    was_flagged: Mapped[bool] = mapped_column(default=False, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(nullable=False)
    retry_of: Mapped[int | None] = mapped_column(
        ForeignKey("practice_responses.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    session: Mapped["PracticeSession"] = relationship(back_populates="responses")
    question: Mapped["Question"] = relationship(back_populates="practice_responses")
    selected_answer: Mapped["Answer | None"] = relationship(
        back_populates="practice_responses",
    )

    def __repr__(self) -> str:
        return f"<PracticeResponse(id={self.id}, session={self.session_id}, correct={self.is_correct})>"
