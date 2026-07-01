"""Exam model for organizing exam documents."""

import uuid as _uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.exam_image import ExamImage
    from app.models.practice_session import PracticeSession
    from app.models.question import Question
    from app.models.subject import Subject


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
        Index("idx_exam_subject_id", "subject_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Cross-DB identity used by the export/import flow. Stable across
    # databases; default is Python uuid4() so service code that does
    # not pass an explicit uuid still gets a unique value at INSERT.
    uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        default=lambda: str(_uuid.uuid4()),
        nullable=False,
    )
    partial_number: Mapped[int] = mapped_column(nullable=False)
    exam_date: Mapped[date | None] = mapped_column(nullable=True)
    topic_tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Relationships
    subject: Mapped["Subject"] = relationship(
        back_populates="exams",
    )
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
        return f"<Exam(id={self.id}, partial={self.partial_number}, date={self.exam_date}, subject_id={self.subject_id})>"
