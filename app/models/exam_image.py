"""ExamImage model for storing uploaded exam images."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import OCRStatus
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.exam import Exam
    from app.models.question import Question


class ExamImage(Base):
    """ExamImage model for uploaded exam images."""

    __tablename__ = "exam_images"

    __table_args__ = (
        Index("idx_exam_image_exam", "exam_id"),
        Index("idx_exam_image_status", "ocr_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_path: Mapped[str] = mapped_column(String(500), nullable=False)
    ocr_status: Mapped[str] = mapped_column(
        String(20),
        default=OCRStatus.PENDING.value,
        nullable=False,
    )

    # Relationships
    exam: Mapped["Exam"] = relationship(back_populates="images")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="image",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ExamImage(id={self.id}, exam_id={self.exam_id}, status={self.ocr_status})>"
