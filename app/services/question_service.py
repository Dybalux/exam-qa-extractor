"""Question Service for CRUD operations on exam questions."""

import logging
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.exam import Exam
from app.models.question import Question
from app.models.topic import Topic

logger = logging.getLogger(__name__)


class QuestionService:
    """Service for question CRUD operations."""

    def __init__(self, session: AsyncSession):
        """Initialize question service.

        Args:
            session: Database session
        """
        self.session = session

    async def _resolve_topic_id(self, topic_slug: str) -> int:
        """Resolve a topic slug to its database ID.

        Args:
            topic_slug: The topic slug (e.g. 'processes').

        Returns:
            The topic's primary key ID.

        Raises:
            ValidationError: If no Topic matches the given slug.
        """
        result = await self.session.execute(
            select(Topic).where(Topic.slug == topic_slug)
        )
        topic = result.scalar_one_or_none()
        if topic is None:
            available = await self.session.execute(
                select(Topic.slug).order_by(Topic.slug)
            )
            slugs = [row[0] for row in available.fetchall()]
            raise ValidationError(
                f"Invalid topic: {topic_slug}",
                details={"valid_topics": slugs},
            )
        return topic.id

    async def create_question(
        self,
        exam_id: int,
        question_text: str,
        topic: str = "other",
        order_in_exam: int | None = None,
        image_id: int | None = None,
        extracted_text: str | None = None,
        confidence_score: float | None = None,
    ) -> Question:
        """Create a new question for an exam.

        Args:
            exam_id: Exam ID
            question_text: Text of the question
            topic: Topic slug (resolved to topic_id dynamically).
            order_in_exam: Position in the exam (1-50)
            image_id: Optional source image ID
            extracted_text: Raw OCR-extracted text
            confidence_score: OCR confidence score

        Returns:
            Created question

        Raises:
            NotFoundError: If exam not found
            ValidationError: If parameters are invalid or topic slug unknown
        """
        result = await self.session.execute(select(Exam).where(Exam.id == exam_id))
        if not result.scalar_one_or_none():
            raise NotFoundError(f"Exam not found: {exam_id}")

        if not question_text.strip():
            raise ValidationError("question_text cannot be empty")

        if order_in_exam is not None and not (1 <= order_in_exam <= 50):
            raise ValidationError(
                "order_in_exam must be between 1 and 50",
                details={"order_in_exam": order_in_exam},
            )

        topic_id = await self._resolve_topic_id(topic)

        question = Question(
            exam_id=exam_id,
            question_text=question_text.strip(),
            topic_id=topic_id,
            order_in_exam=order_in_exam,
            image_id=image_id,
            extracted_text=extracted_text,
            confidence_score=confidence_score,
        )

        self.session.add(question)
        await self.session.commit()
        await self.session.refresh(question)

        logger.info(
            f"Created question {question.id} for exam {exam_id} (topic={topic})"
        )
        return question

    async def get_question(self, question_id: int) -> Question:
        """Get question by ID.

        Args:
            question_id: Question ID

        Returns:
            Question instance

        Raises:
            NotFoundError: If question not found
        """
        result = await self.session.execute(
            select(Question).where(Question.id == question_id)
        )
        question = result.scalar_one_or_none()

        if not question:
            raise NotFoundError(f"Question not found: {question_id}")

        return question

    async def list_questions(
        self,
        exam_id: int | None = None,
        topic: str | None = None,
        is_corrected: bool | None = None,
        is_ready_for_practice: bool | None = None,
    ) -> Sequence[Question]:
        """List questions with optional filtering.

        Args:
            exam_id: Filter by exam ID
            topic: Filter by topic slug (joined on topics table).
            is_corrected: Filter by correction status
            is_ready_for_practice: Filter by practice readiness (has correct answer)

        Returns:
            List of questions
        """
        query = select(Question)

        if exam_id is not None:
            query = query.where(Question.exam_id == exam_id)

        if topic is not None:
            query = query.join(Topic, Question.topic_id == Topic.id).where(
                Topic.slug == topic
            )

        if is_corrected is not None:
            query = query.where(Question.is_corrected == is_corrected)

        query = query.order_by(
            Question.order_in_exam.asc().nullslast(), Question.id.asc()
        )

        result = await self.session.execute(query)
        questions = list(result.scalars().all())

        # Filter by practice readiness in Python (requires loaded answers via selectin)
        if is_ready_for_practice is not None:
            questions = [
                q for q in questions if q.is_ready_for_practice == is_ready_for_practice
            ]

        return questions

    async def update_question(
        self,
        question_id: int,
        question_text: str | None = None,
        topic: str | None = None,
        order_in_exam: int | None = None,
        correction_notes: str | None = None,
        is_corrected: bool | None = None,
        has_code_in_answers: bool | None = None,
    ) -> Question:
        """Update question fields.

        Args:
            question_id: Question ID
            question_text: New question text
            topic: New topic classification
            order_in_exam: New position in exam (1-50)
            correction_notes: Notes about the correction
            is_corrected: Mark as manually corrected
            has_code_in_answers: Whether answers contain code

        Returns:
            Updated question

        Raises:
            NotFoundError: If question not found
            ValidationError: If parameters are invalid
        """
        question = await self.get_question(question_id)

        if question_text is not None:
            if not question_text.strip():
                raise ValidationError("question_text cannot be empty")
            question.question_text = question_text.strip()

        if topic is not None:
            topic_id = await self._resolve_topic_id(topic)
            question.topic_id = topic_id

        if order_in_exam is not None:
            if not (1 <= order_in_exam <= 50):
                raise ValidationError(
                    "order_in_exam must be between 1 and 50",
                    details={"order_in_exam": order_in_exam},
                )
            question.order_in_exam = order_in_exam

        if correction_notes is not None:
            question.correction_notes = correction_notes

        if is_corrected is not None:
            question.is_corrected = is_corrected

        if has_code_in_answers is not None:
            question.has_code_in_answers = has_code_in_answers

        await self.session.commit()
        await self.session.refresh(question)

        logger.info(f"Updated question {question_id}")
        return question

    async def correct_ocr_text(
        self,
        question_id: int,
        corrected_text: str,
        notes: str | None = None,
    ) -> Question:
        """Mark OCR-extracted text as manually corrected.

        Args:
            question_id: Question ID
            corrected_text: The corrected question text
            notes: Optional notes about what was corrected

        Returns:
            Updated question

        Raises:
            NotFoundError: If question not found
        """
        return await self.update_question(
            question_id=question_id,
            question_text=corrected_text,
            is_corrected=True,
            correction_notes=notes,
        )

    async def delete_question(self, question_id: int) -> bool:
        """Delete a question and its answers (cascade).

        Args:
            question_id: Question ID

        Returns:
            True if deleted

        Raises:
            NotFoundError: If question not found
        """
        question = await self.get_question(question_id)

        await self.session.delete(question)
        await self.session.commit()

        logger.info(f"Deleted question {question_id}")
        return True

    async def bulk_create_from_ocr(
        self,
        exam_id: int,
        questions_data: list[dict],
        image_id: int | None = None,
    ) -> list[Question]:
        """Bulk create questions from OCR extraction results.

        Args:
            exam_id: Exam ID
            questions_data: List of dicts with keys: question_text, extracted_text,
                            confidence_score, topic, order_in_exam
            image_id: Optional source image ID

        Returns:
            List of created questions

        Raises:
            NotFoundError: If exam not found
            ValidationError: If questions_data is empty
        """
        if not questions_data:
            raise ValidationError("questions_data cannot be empty")

        result = await self.session.execute(select(Exam).where(Exam.id == exam_id))
        if not result.scalar_one_or_none():
            raise NotFoundError(f"Exam not found: {exam_id}")

        # Pre-fetch all topic slugs → ids to avoid N+1 lookups.
        topic_rows = await self.session.execute(select(Topic.slug, Topic.id))
        topic_map: dict[str, int] = {slug: tid for slug, tid in topic_rows.fetchall()}

        questions = []
        for i, data in enumerate(questions_data, start=1):
            topic_slug = data.get("topic", "other")
            topic_id = topic_map.get(topic_slug)
            if topic_id is None:
                raise ValidationError(
                    f"Invalid topic: {topic_slug}",
                    details={"valid_topics": list(topic_map.keys())},
                )
            question = Question(
                exam_id=exam_id,
                image_id=image_id,
                question_text=data.get("question_text", "").strip(),
                extracted_text=data.get("extracted_text"),
                confidence_score=data.get("confidence_score"),
                topic_id=topic_id,
                order_in_exam=data.get("order_in_exam", i),
            )
            self.session.add(question)
            questions.append(question)

        await self.session.commit()

        for q in questions:
            await self.session.refresh(q)

        logger.info(f"Bulk created {len(questions)} questions for exam {exam_id}")
        return questions
