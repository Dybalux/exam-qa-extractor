"""Question model for extracted exam questions."""

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import TopicEnum
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.answer import Answer
    from app.models.exam import Exam
    from app.models.exam_image import ExamImage
    from app.models.practice_response import PracticeResponse


class Question(Base):
    """Question model for exam questions."""

    __tablename__ = "questions"

    __table_args__ = (
        CheckConstraint(
            "difficulty BETWEEN 1 AND 5",
            name="check_valid_difficulty",
        ),
        CheckConstraint(
            "order_in_exam BETWEEN 1 AND 50",
            name="check_valid_order",
        ),
        Index("idx_question_exam", "exam_id"),
        Index("idx_question_topic", "topic"),
        Index("idx_question_corrected", "is_corrected"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_id: Mapped[int | None] = mapped_column(
        ForeignKey("exam_images.id", ondelete="SET NULL"),
        nullable=True,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    topic: Mapped[str] = mapped_column(
        String(50),
        default=TopicEnum.OTHER.value,
        nullable=False,
    )
    order_in_exam: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_corrected: Mapped[bool] = mapped_column(default=False, nullable=False)
    correction_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[int] = mapped_column(default=3, nullable=False)
    has_code_in_answers: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relationships
    exam: Mapped["Exam"] = relationship(back_populates="questions")
    image: Mapped["ExamImage | None"] = relationship(back_populates="questions")
    answers: Mapped[list["Answer"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    practice_responses: Mapped[list["PracticeResponse"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Question(id={self.id}, exam_id={self.exam_id}, topic={self.topic})>"

    @property
    def correct_answer(self) -> "Answer | None":
        """Get the correct answer for this question."""
        from app.core.constants import AnswerType
        for answer in self.answers:
            if answer.answer_type == AnswerType.CORRECT.value:
                return answer
        return None

    @property
    def is_ready_for_practice(self) -> bool:
        """Check if question has at least one correct answer."""
        return self.correct_answer is not None
