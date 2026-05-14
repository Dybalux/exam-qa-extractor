"""Exam model for organizing exam documents."""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.answer import Answer
    from app.models.exam_image import ExamImage
    from app.models.practice_session import PracticeSession
    from app.models.question import Question


class Exam(Base):
    """Exam model representing a partial exam document."""

    __tablename__ = "exams"

    __table_args__ = (
        CheckConstraint(
            "partial_number IN (1, 2, 3, 4)",
            name="check_valid_partial_number",
        ),
        Index("idx_exam_partial", "partial_number"),
        Index("idx_exam_date", "exam_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    partial_number: Mapped[int] = mapped_column(nullable=False)
    exam_date: Mapped[date | None] = mapped_column(nullable=True)
    topic_tags: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    images: Mapped[list["ExamImage"]] = relationship(
        back_populates="exam",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    questions: Mapped[list["Question"]] = relationship(
        back_populates="exam",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    practice_sessions: Mapped[list["PracticeSession"]] = relationship(
        back_populates="exam",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Exam(id={self.id}, partial={self.partial_number}, date={self.exam_date})>"
