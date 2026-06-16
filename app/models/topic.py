"""Topic model representing a subject topic/category."""

import uuid as _uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.question import Question
    from app.models.subject import Subject


class Topic(Base):
    """Topic model for questions."""

    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        default=lambda: str(_uuid.uuid4()),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    subject: Mapped["Subject"] = relationship(back_populates="topics")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="topic_relation",
        lazy="selectin",
    )

    def __init__(self, **kwargs: Any) -> None:
        """Initialize Topic and auto-generate slug if not provided."""
        super().__init__(**kwargs)
        if not self.slug and self.name:
            from app.core.slug import slugify

            self.slug = slugify(self.name)

    def __repr__(self) -> str:
        return f"<Topic(id={self.id}, name='{self.name}', slug='{self.slug}', subject_id={self.subject_id})>"
