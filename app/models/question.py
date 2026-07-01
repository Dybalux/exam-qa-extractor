"""Question model for extracted exam questions."""

import uuid as _uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.answer import Answer
    from app.models.exam import Exam
    from app.models.exam_image import ExamImage
    from app.models.practice_response import PracticeResponse
    from app.models.topic import Topic


class Question(Base):
    """Question model for exam questions."""

    __tablename__ = "questions"

    __table_args__ = (
        CheckConstraint(
            "order_in_exam BETWEEN 1 AND 50",
            name="check_valid_order",
        ),
        Index("idx_question_exam", "exam_id"),
        Index("idx_question_topic", "topic"),
        Index("idx_question_corrected", "is_corrected"),
        Index("idx_question_topic_id", "topic_id"),
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
    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
    )
    _topic: Mapped[str] = mapped_column(
        "topic",
        String(50),
        default="other",
        nullable=False,
    )
    order_in_exam: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_corrected: Mapped[bool] = mapped_column(default=False, nullable=False)
    correction_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_code_in_answers: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relationships
    exam: Mapped["Exam"] = relationship(back_populates="questions")
    image: Mapped["ExamImage | None"] = relationship(back_populates="questions")
    topic_relation: Mapped["Topic | None"] = relationship(
        back_populates="questions",
        lazy="selectin",
    )
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

    def __init__(self, **kwargs: Any) -> None:
        """Initialize Question and handle deprecated topic keyword argument."""
        topic_val = kwargs.pop("topic", None)
        super().__init__(**kwargs)
        if topic_val is not None:
            self.topic = topic_val  # type: ignore[method-assign]

    @hybrid_property
    def topic(self) -> str:
        """Get the topic slug from the relation or fallback to the deprecated field."""
        if self.topic_relation:
            return self.topic_relation.slug
        return self._topic

    @topic.setter  # type: ignore[no-redef]
    def topic(self, value: str) -> None:
        """Set the topic value."""
        self._topic = value

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
