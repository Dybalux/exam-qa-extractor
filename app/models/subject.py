"""Subject model representing a course or study subject."""

import uuid as _uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.exam import Exam
    from app.models.topic import Topic


class Subject(Base):
    """Subject model representing a course (e.g., 'Sistemas Operativos')."""

    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        default=lambda: str(_uuid.uuid4()),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )

    # Relationships
    topics: Mapped[list["Topic"]] = relationship(
        back_populates="subject",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    exams: Mapped[list["Exam"]] = relationship(
        back_populates="subject",
        lazy="selectin",
    )

    def __init__(self, **kwargs: Any) -> None:
        """Initialize Subject and auto-generate slug if not provided."""
        super().__init__(**kwargs)
        if not self.slug and self.name:
            from app.core.slug import slugify

            self.slug = slugify(self.name)

    def __repr__(self) -> str:
        return f"<Subject(id={self.id}, name='{self.name}', slug='{self.slug}')>"
