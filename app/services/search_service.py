"""Search Service for querying questions across exams."""

import logging
from typing import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import CONFIDENCE_MEDIUM, TopicEnum
from app.models.exam import Exam
from app.models.question import Question

logger = logging.getLogger(__name__)


class SearchService:
    """Service for searching and filtering questions."""

    def __init__(self, session: AsyncSession):
        """Initialize search service.

        Args:
            session: Database session
        """
        self.session = session

    async def search_questions(
        self,
        query: str,
        topic: str | None = None,
        exam_id: int | None = None,
        partial_number: int | None = None,
        limit: int = 20,
    ) -> Sequence[Question]:
        """Full-text search across question text and extracted text.

        Args:
            query: Search term
            topic: Optional topic filter
            exam_id: Optional exam filter
            partial_number: Optional partial number filter (1-4)
            limit: Maximum results to return

        Returns:
            Matching questions ordered by relevance (exact matches first)
        """
        if not query.strip():
            return []

        term = f"%{query.strip()}%"

        stmt = select(Question).where(
            or_(
                Question.question_text.ilike(term),
                Question.extracted_text.ilike(term),
                Question.correction_notes.ilike(term),
            )
        )

        if topic is not None:
            stmt = stmt.where(Question.topic == topic)

        if exam_id is not None:
            stmt = stmt.where(Question.exam_id == exam_id)

        if partial_number is not None:
            stmt = stmt.join(Exam, Question.exam_id == Exam.id).where(
                Exam.partial_number == partial_number
            )

        stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        questions = result.scalars().all()

        logger.info(
            f"Search '{query}' returned {len(questions)} results "
            f"(topic={topic}, exam_id={exam_id})"
        )
        return questions

    async def get_questions_needing_review(
        self,
        exam_id: int | None = None,
        confidence_threshold: float = CONFIDENCE_MEDIUM,
    ) -> Sequence[Question]:
        """Get questions that need human review.

        A question needs review if it has not been manually corrected
        AND its OCR confidence score is below the threshold (or missing).

        Args:
            exam_id: Optional exam filter
            confidence_threshold: Minimum acceptable confidence score

        Returns:
            Questions needing review, ordered by confidence score ascending
        """
        stmt = select(Question).where(Question.is_corrected == False)  # noqa: E712

        if exam_id is not None:
            stmt = stmt.where(Question.exam_id == exam_id)

        # Prioritise low-confidence and unknown-confidence questions
        stmt = stmt.where(
            or_(
                Question.confidence_score == None,  # noqa: E711
                Question.confidence_score < confidence_threshold,
            )
        ).order_by(Question.confidence_score.asc().nullsfirst())

        result = await self.session.execute(stmt)
        questions = result.scalars().all()

        logger.info(
            f"Found {len(questions)} questions needing review "
            f"(threshold={confidence_threshold})"
        )
        return questions

    async def get_questions_without_answers(
        self,
        exam_id: int | None = None,
        topic: str | None = None,
    ) -> Sequence[Question]:
        """Get questions that have no answers added yet (not ready for practice).

        Args:
            exam_id: Optional exam filter
            topic: Optional topic filter

        Returns:
            Questions without any correct answer, ordered by exam and position
        """
        stmt = select(Question)

        if exam_id is not None:
            stmt = stmt.where(Question.exam_id == exam_id)

        if topic is not None:
            stmt = stmt.where(Question.topic == topic)

        stmt = stmt.order_by(Question.exam_id.asc(), Question.order_in_exam.asc().nullslast())

        result = await self.session.execute(stmt)
        all_questions = result.scalars().all()

        # Filter in Python — requires selectin-loaded answers
        without_answers = [q for q in all_questions if not q.is_ready_for_practice]

        logger.info(
            f"Found {len(without_answers)} questions without correct answers"
        )
        return without_answers

    async def search_by_topic(
        self,
        topic: str,
        limit: int = 50,
    ) -> Sequence[Question]:
        """Get all questions for a given topic across all exams.

        Args:
            topic: Topic value from TopicEnum
            limit: Maximum results

        Returns:
            Questions matching the topic

        Raises:
            ValueError: If topic is not a valid TopicEnum value
        """
        valid_topics = {t.value for t in TopicEnum}
        if topic not in valid_topics:
            raise ValueError(
                f"Invalid topic: {topic}. Valid: {sorted(valid_topics)}"
            )

        result = await self.session.execute(
            select(Question)
            .where(Question.topic == topic)
            .order_by(Question.exam_id.asc(), Question.order_in_exam.asc().nullslast())
            .limit(limit)
        )
        questions = result.scalars().all()

        logger.info(f"Topic '{topic}' returned {len(questions)} questions")
        return questions

    async def get_low_confidence_questions(
        self,
        threshold: float = CONFIDENCE_MEDIUM,
        exam_id: int | None = None,
        limit: int = 30,
    ) -> Sequence[Question]:
        """Get questions with low OCR confidence, regardless of correction status.

        Args:
            threshold: Maximum confidence score to include
            exam_id: Optional exam filter
            limit: Maximum results

        Returns:
            Questions ordered by confidence score ascending (worst first)
        """
        stmt = select(Question).where(
            or_(
                Question.confidence_score == None,  # noqa: E711
                Question.confidence_score < threshold,
            )
        )

        if exam_id is not None:
            stmt = stmt.where(Question.exam_id == exam_id)

        stmt = stmt.order_by(
            Question.confidence_score.asc().nullsfirst()
        ).limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all()
