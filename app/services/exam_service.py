"""Exam Service for CRUD operations on exams."""

import logging
from datetime import date
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.exam import Exam
from app.models.subject import Subject

logger = logging.getLogger(__name__)


class ExamService:
    """Service for exam CRUD operations."""

    def __init__(self, session: AsyncSession):
        """Initialize exam service.

        Args:
            session: Database session
        """
        self.session = session

    async def _resolve_subject_id(self, subject_id: int | None) -> int:
        """Resolve subject_id, defaulting to 'sistemas-operativos'.

        Args:
            subject_id: Optional explicit subject ID.

        Returns:
            The resolved subject's primary key.

        Raises:
            NotFoundError: If an explicit subject_id is provided but not found.
        """
        if subject_id is not None:
            result = await self.session.execute(
                select(Subject).where(Subject.id == subject_id)
            )
            subj = result.scalar_one_or_none()
            if subj is None:
                raise NotFoundError(f"Subject not found: {subject_id}")
            return subj.id

        # Default: resolve by slug.
        result = await self.session.execute(
            select(Subject).where(Subject.slug == "sistemas-operativos")
        )
        subj = result.scalar_one_or_none()
        if subj is None:
            # Create the default subject on-the-fly if missing
            subj = Subject(name="Sistemas Operativos", slug="sistemas-operativos")
            self.session.add(subj)
            await self.session.flush()
        return subj.id

    async def create_exam(
        self,
        partial_number: int,
        exam_date: date | None = None,
        topic_tags: str | None = None,
        subject_id: int | None = None,
    ) -> Exam:
        """Create a new exam.

        Args:
            partial_number: Partial number (1-4)
            exam_date: Optional exam date
            topic_tags: Optional comma-separated topic tags
            subject_id: Optional subject ID. Defaults to 'sistemas-operativos'.

        Returns:
            Created exam

        Raises:
            ValidationError: If partial_number is invalid
            ConflictError: If duplicate exam exists
            NotFoundError: If subject_id is provided but not found
        """
        # Validate partial number
        if partial_number not in [1, 2, 3, 4]:
            raise ValidationError(
                "partial_number must be 1, 2, 3, or 4",
                details={"partial_number": partial_number},
            )

        # Check for duplicate (same partial and date)
        if exam_date:
            existing = await self.session.execute(
                select(Exam).where(
                    Exam.partial_number == partial_number,
                    Exam.exam_date == exam_date,
                )
            )
            if existing.scalar_one_or_none():
                raise ConflictError(
                    f"Exam already exists for partial {partial_number} on {exam_date}",
                    details={
                        "partial_number": partial_number,
                        "exam_date": str(exam_date),
                    },
                )

        # Resolve subject_id (default to sistemas-operativos)
        resolved_subject_id = await self._resolve_subject_id(subject_id)

        # Create exam
        exam = Exam(
            partial_number=partial_number,
            exam_date=exam_date,
            topic_tags=topic_tags,
            subject_id=resolved_subject_id,
        )

        self.session.add(exam)
        await self.session.commit()
        await self.session.refresh(exam)

        logger.info(f"Created exam {exam.id} (partial {partial_number})")
        return exam

    async def get_exam(self, exam_id: int) -> Exam:
        """Get exam by ID.

        Args:
            exam_id: Exam ID

        Returns:
            Exam instance

        Raises:
            NotFoundError: If exam not found
        """
        result = await self.session.execute(select(Exam).where(Exam.id == exam_id))
        exam = result.scalar_one_or_none()

        if not exam:
            raise NotFoundError(f"Exam not found: {exam_id}")

        return exam

    async def list_exams(
        self,
        partial_number: int | None = None,
        topic: str | None = None,
    ) -> Sequence[Exam]:
        """List exams with optional filtering.

        Args:
            partial_number: Filter by partial number
            topic: Filter by topic tag

        Returns:
            List of exams
        """
        query = select(Exam)

        if partial_number is not None:
            query = query.where(Exam.partial_number == partial_number)

        if topic:
            # Search in topic_tags (comma-separated)
            query = query.where(Exam.topic_tags.ilike(f"%{topic}%"))

        query = query.order_by(Exam.exam_date.desc().nullslast())

        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_exam(
        self,
        exam_id: int,
        partial_number: int | None = None,
        exam_date: date | None = None,
        topic_tags: str | None = None,
        clear_exam_date: bool = False,
    ) -> Exam:
        """Update exam metadata.

        Args:
            exam_id: Exam ID
            partial_number: New partial number 1-4 (optional)
            exam_date: New exam date (optional)
            topic_tags: New topic tags (optional)
            clear_exam_date: Set the date to NULL (``exam_date=None`` alone
                means "leave unchanged", so clearing must be explicit)

        Returns:
            Updated exam
        """
        exam = await self.get_exam(exam_id)

        if partial_number is not None:
            exam.partial_number = partial_number

        if clear_exam_date:
            exam.exam_date = None
        elif exam_date is not None:
            exam.exam_date = exam_date

        if topic_tags is not None:
            exam.topic_tags = topic_tags

        await self.session.commit()
        await self.session.refresh(exam)

        logger.info(f"Updated exam {exam_id}")
        return exam

    async def delete_exam(self, exam_id: int, force: bool = False) -> bool:
        """Delete an exam.

        Args:
            exam_id: Exam ID
            force: If True, delete even if questions exist

        Returns:
            True if deleted

        Raises:
            NotFoundError: If exam not found
            ConflictError: If exam has questions and force=False
        """
        exam = await self.get_exam(exam_id)

        # Check for questions
        question_count = len(exam.questions)
        if question_count > 0 and not force:
            raise ConflictError(
                f"Cannot delete exam with {question_count} questions. "
                "Use force=true to delete anyway.",
                details={
                    "exam_id": exam_id,
                    "question_count": question_count,
                },
            )

        await self.session.delete(exam)
        await self.session.commit()

        logger.info(f"Deleted exam {exam_id} (force={force})")
        return True
