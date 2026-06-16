"""Exam Service for CRUD operations on exams."""

import logging
from datetime import date
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.exam import Exam

logger = logging.getLogger(__name__)


class ExamService:
    """Service for exam CRUD operations."""

    def __init__(self, session: AsyncSession):
        """Initialize exam service.

        Args:
            session: Database session
        """
        self.session = session

    async def create_exam(
        self,
        partial_number: int,
        exam_date: date | None = None,
        topic_tags: str | None = None,
    ) -> Exam:
        """Create a new exam.

        Args:
            partial_number: Partial number (1-4)
            exam_date: Optional exam date
            topic_tags: Optional comma-separated topic tags

        Returns:
            Created exam

        Raises:
            ValidationError: If partial_number is invalid
            ConflictError: If duplicate exam exists
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

        # Create exam
        exam = Exam(
            partial_number=partial_number,
            exam_date=exam_date,
            topic_tags=topic_tags,
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
    ) -> Exam:
        """Update exam metadata.

        Args:
            exam_id: Exam ID
            partial_number: New partial number 1-4 (optional)
            exam_date: New exam date (optional)
            topic_tags: New topic tags (optional)

        Returns:
            Updated exam
        """
        exam = await self.get_exam(exam_id)

        if partial_number is not None:
            exam.partial_number = partial_number

        if exam_date is not None:
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

    async def get_exam_stats(self, exam_id: int) -> dict:
        """Get statistics for an exam.

        Args:
            exam_id: Exam ID

        Returns:
            Dictionary with statistics
        """
        exam = await self.get_exam(exam_id)

        questions = exam.questions
        total_questions = len(questions)

        # Count by topic
        topic_counts = {}
        for q in questions:
            topic = q.topic
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

        # Count ready for practice
        ready_count = sum(1 for q in questions if q.is_ready_for_practice)

        return {
            "exam_id": exam_id,
            "partial_number": exam.partial_number,
            "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
            "topic_tags": exam.topic_tags,
            "total_questions": total_questions,
            "questions_by_topic": topic_counts,
            "ready_for_practice": ready_count,
            "needs_answers": total_questions - ready_count,
        }

    async def add_tags(self, exam_id: int, new_tags: list[str]) -> Exam:
        """Add topic tags to an exam.

        Args:
            exam_id: Exam ID
            new_tags: List of tags to add

        Returns:
            Updated exam
        """
        exam = await self.get_exam(exam_id)

        # Get existing tags
        existing = set()
        if exam.topic_tags:
            existing = set(tag.strip() for tag in exam.topic_tags.split(","))

        # Add new tags
        existing.update(tag.strip() for tag in new_tags)

        # Update
        exam.topic_tags = ",".join(sorted(existing))

        await self.session.commit()
        await self.session.refresh(exam)

        return exam

    async def remove_tags(self, exam_id: int, tags_to_remove: list[str]) -> Exam:
        """Remove topic tags from an exam.

        Args:
            exam_id: Exam ID
            tags_to_remove: List of tags to remove

        Returns:
            Updated exam
        """
        exam = await self.get_exam(exam_id)

        if not exam.topic_tags:
            return exam

        # Get existing tags
        existing = set(tag.strip() for tag in exam.topic_tags.split(","))

        # Remove tags
        to_remove = set(tag.strip() for tag in tags_to_remove)
        existing -= to_remove

        # Update
        exam.topic_tags = ",".join(sorted(existing)) if existing else None

        await self.session.commit()
        await self.session.refresh(exam)

        return exam
