"""Answer model for question answers."""

import uuid as _uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AnswerType
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.practice_response import PracticeResponse
    from app.models.question import Question


class Answer(Base):
    """Answer model for question answers."""

    __tablename__ = "answers"

    __table_args__ = (
        CheckConstraint(
            "answer_type IN ('correct', 'incorrect', 'partial')",
            name="check_valid_answer_type",
        ),
        Index("idx_answer_question", "question_id"),
        Index("idx_answer_type", "answer_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Cross-DB identity used by the export/import flow. See app.models.exam.
    uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        default=lambda: str(_uuid.uuid4()),
        nullable=False,
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_type: Mapped[str] = mapped_column(
        String(20),
        default=AnswerType.INCORRECT.value,
        nullable=False,
    )
    is_common_misconception: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationships
    question: Mapped["Question"] = relationship(back_populates="answers")
    practice_responses: Mapped[list["PracticeResponse"]] = relationship(
        back_populates="selected_answer",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Answer(id={self.id}, question_id={self.question_id}, type={self.answer_type})>"

    @property
    def is_correct(self) -> bool:
        """Check if this is a correct answer."""
        return self.answer_type == AnswerType.CORRECT.value
