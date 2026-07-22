"""Practice Service for managing interactive study sessions."""

import logging
import random
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import AnswerType, PracticeMode
from app.core.exceptions import NotFoundError, ValidationError
from app.models.answer import Answer
from app.models.practice_response import PracticeResponse
from app.models.practice_session import PracticeSession
from app.models.question import Question

logger = logging.getLogger(__name__)


class PracticeService:
    """Service for managing practice sessions."""

    def __init__(self, session: AsyncSession):
        """Initialize practice service.

        Args:
            session: Database session
        """
        self.session = session

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def create_session(
        self,
        user_session_id: str,
        mode: str = PracticeMode.RANDOM.value,
        exam_id: int | None = None,
        filters: dict | None = None,
        total_questions: int = 10,
    ) -> PracticeSession:
        """Create a new practice session.

        Args:
            user_session_id: Browser/user session identifier
            mode: Practice mode (random, by_partial, by_topic, exam_simulation)
            exam_id: Optional exam to restrict questions
            filters: Optional dict with keys: topic
            total_questions: Number of questions for this session (1-100)

        Returns:
            Created practice session

        Raises:
            ValidationError: If parameters invalid or no questions available
        """
        valid_modes = {m.value for m in PracticeMode}
        if mode not in valid_modes:
            raise ValidationError(
                f"Invalid mode: {mode}",
                details={"valid_modes": list(valid_modes)},
            )

        if not (1 <= total_questions <= 100):
            raise ValidationError(
                "total_questions must be between 1 and 100",
                details={"total_questions": total_questions},
            )

        # Error review mode: pre-filter pool to previously failed questions
        question_ids = None
        if mode == PracticeMode.ERROR_REVIEW.value:
            question_ids = await self._get_failed_question_ids(user_session_id)
            # Early guard: no prior failures means error_review has nothing to
            # review. Raise explicitly rather than relying on the empty-list
            # filter behaviour in _get_available_questions.
            if not question_ids:
                raise ValidationError(
                    "No questions with previous errors found.",
                )

        available = await self._get_available_questions(
            exam_id=exam_id, filters=filters or {}, question_ids=question_ids
        )

        if not available:
            if mode == PracticeMode.ERROR_REVIEW.value:
                raise ValidationError(
                    "No questions with previous errors found.",
                )
            raise ValidationError(
                "No questions available for the selected filters. "
                "Ensure questions have at least one correct answer.",
                details={"filters": filters, "exam_id": exam_id},
            )

        actual_total = min(total_questions, len(available))

        practice_session = PracticeSession(
            user_session_id=user_session_id,
            mode=mode,
            exam_id=exam_id,
            filters=filters,
            total_questions=actual_total,
            started_at=datetime.now(timezone.utc),
        )

        self.session.add(practice_session)
        await self.session.commit()
        await self.session.refresh(practice_session)

        logger.info(
            f"Created practice session {practice_session.id} "
            f"(user={user_session_id[:8]}..., mode={mode}, total={actual_total})"
        )
        return practice_session

    async def get_session(self, session_id: int) -> PracticeSession:
        """Get a practice session by ID.

        Args:
            session_id: Session ID

        Returns:
            PracticeSession instance

        Raises:
            NotFoundError: If session not found
        """
        result = await self.session.execute(
            select(PracticeSession).where(PracticeSession.id == session_id)
        )
        practice_session = result.scalar_one_or_none()

        if not practice_session:
            raise NotFoundError(f"Practice session not found: {session_id}")

        return practice_session

    async def complete_session(self, session_id: int) -> PracticeSession:
        """Mark a practice session as completed.

        Args:
            session_id: Session ID

        Returns:
            Updated session

        Raises:
            NotFoundError: If session not found
            ValidationError: If session already completed
        """
        practice_session = await self.get_session(session_id)

        if practice_session.is_completed:
            raise ValidationError(f"Session {session_id} is already completed")

        now = datetime.now(timezone.utc)
        practice_session.completed_at = now

        started_at = practice_session.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)

        elapsed = now - started_at
        practice_session.total_time_seconds = int(elapsed.total_seconds())

        await self.session.commit()
        await self.session.refresh(practice_session)

        logger.info(
            f"Completed session {session_id} "
            f"(accuracy={practice_session.accuracy:.1f}%, "
            f"time={practice_session.total_time_seconds}s)"
        )
        return practice_session

    # ------------------------------------------------------------------
    # Question flow
    # ------------------------------------------------------------------

    async def get_next_question(self, session_id: int) -> Question | None:
        """Get the next unanswered question for a session.

        Args:
            session_id: Session ID

        Returns:
            Next question or None if session is complete

        Raises:
            NotFoundError: If session not found
        """
        practice_session = await self.get_session(session_id)

        if practice_session.is_completed:
            return None

        if practice_session.questions_answered >= practice_session.total_questions:
            return None

        # IDs already responded in this session
        answered_result = await self.session.execute(
            select(PracticeResponse.question_id).where(
                PracticeResponse.session_id == session_id
            )
        )
        answered_ids = set(answered_result.scalars().all())

        # For error_review mode, recompute failed question IDs
        question_ids = None
        if practice_session.mode == PracticeMode.ERROR_REVIEW.value:
            question_ids = await self._get_failed_question_ids(
                practice_session.user_session_id
            )

        available = await self._get_available_questions(
            exam_id=practice_session.exam_id,
            filters=practice_session.filters or {},
            question_ids=question_ids,
        )

        remaining = [q for q in available if q.id not in answered_ids]

        if not remaining:
            return None

        return random.choice(remaining)

    # ------------------------------------------------------------------
    # Answer submission
    # ------------------------------------------------------------------

    async def submit_answer(
        self,
        session_id: int,
        question_id: int,
        selected_answer_id: int,
        time_spent_seconds: int = 0,
        was_flagged: bool = False,
    ) -> PracticeResponse:
        """Submit an answer for a question in the session.

        Args:
            session_id: Session ID
            question_id: Question being answered
            selected_answer_id: ID of the selected answer
            time_spent_seconds: Time spent on this question
            was_flagged: Whether the user flagged this question for review

        Returns:
            Created practice response

        Raises:
            NotFoundError: If session, question, or answer not found
            ValidationError: If session completed or question already answered
        """
        practice_session = await self.get_session(session_id)

        if practice_session.is_completed:
            raise ValidationError(f"Session {session_id} is already completed")

        # Guard duplicate answer
        existing = await self.session.execute(
            select(PracticeResponse).where(
                PracticeResponse.session_id == session_id,
                PracticeResponse.question_id == question_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationError(
                f"Question {question_id} already answered in session {session_id}"
            )

        # Validate answer belongs to question
        answer_result = await self.session.execute(
            select(Answer).where(Answer.id == selected_answer_id)
        )
        answer = answer_result.scalar_one_or_none()
        if not answer:
            raise NotFoundError(f"Answer not found: {selected_answer_id}")

        if answer.question_id != question_id:
            raise ValidationError(
                f"Answer {selected_answer_id} does not belong to question {question_id}"
            )

        is_correct = answer.answer_type == AnswerType.CORRECT.value

        response = PracticeResponse(
            session_id=session_id,
            question_id=question_id,
            selected_answer_id=selected_answer_id,
            is_correct=is_correct,
            time_spent_seconds=max(0, time_spent_seconds),
            was_flagged=was_flagged,
            answered_at=datetime.now(timezone.utc),
        )

        self.session.add(response)

        # Update session counters
        practice_session.questions_answered += 1
        if is_correct:
            practice_session.correct_count += 1
        else:
            practice_session.incorrect_count += 1

        await self.session.commit()
        await self.session.refresh(response)

        logger.info(
            f"Session {session_id}: answered question {question_id} "
            f"(correct={is_correct})"
        )
        return response

    async def skip_question(
        self,
        session_id: int,
        question_id: int,
        time_spent_seconds: int = 0,
    ) -> PracticeResponse:
        """Skip a question (counts as unanswered/skipped).

        Args:
            session_id: Session ID
            question_id: Question being skipped
            time_spent_seconds: Time spent before skipping

        Returns:
            Created practice response with no selected answer

        Raises:
            NotFoundError: If session not found
            ValidationError: If session completed or question already answered
        """
        practice_session = await self.get_session(session_id)

        if practice_session.is_completed:
            raise ValidationError(f"Session {session_id} is already completed")

        existing = await self.session.execute(
            select(PracticeResponse).where(
                PracticeResponse.session_id == session_id,
                PracticeResponse.question_id == question_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationError(
                f"Question {question_id} already answered in session {session_id}"
            )

        response = PracticeResponse(
            session_id=session_id,
            question_id=question_id,
            selected_answer_id=None,
            is_correct=None,
            time_spent_seconds=max(0, time_spent_seconds),
            answered_at=datetime.now(timezone.utc),
        )

        self.session.add(response)
        practice_session.questions_answered += 1
        practice_session.skipped_count += 1

        await self.session.commit()
        await self.session.refresh(response)

        logger.info(f"Session {session_id}: skipped question {question_id}")
        return response

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    async def get_session_results(self, session_id: int) -> dict:
        """Get full results for a completed or in-progress session.

        Includes per-question detail: question text, selected answer,
        correct answer, and explanation for incorrect responses.

        Args:
            session_id: Session ID

        Returns:
            Dict with session stats and per-question breakdown

        Raises:
            NotFoundError: If session not found
        """
        practice_session = await self.get_session(session_id)

        responses_result = await self.session.execute(
            select(PracticeResponse)
            .options(
                selectinload(PracticeResponse.question).selectinload(Question.answers),
                selectinload(PracticeResponse.selected_answer),
            )
            .where(PracticeResponse.session_id == session_id)
        )
        responses = responses_result.scalars().all()

        return {
            "session_id": session_id,
            "mode": practice_session.mode,
            "is_completed": practice_session.is_completed,
            "total_questions": practice_session.total_questions,
            "questions_answered": practice_session.questions_answered,
            "correct_count": practice_session.correct_count,
            "incorrect_count": practice_session.incorrect_count,
            "skipped_count": practice_session.skipped_count,
            "accuracy": practice_session.accuracy,
            "total_time_seconds": practice_session.total_time_seconds,
            "responses": [self._build_response_detail(r) for r in responses],
        }

    def _build_response_detail(self, r: PracticeResponse) -> dict:
        """Build a detailed per-response dict with question and answer context.

        Args:
            r: PracticeResponse instance with eager-loaded relationships

        Returns:
            Dict with full question/answer detail for the results page
        """
        question = r.question
        selected = r.selected_answer
        correct = question.correct_answer if question else None

        return {
            "question_id": r.question_id,
            "question_text": question.question_text if question else None,
            "selected_answer_id": r.selected_answer_id,
            "selected_answer_text": selected.answer_text if selected else None,
            "is_correct": r.is_correct,
            "correct_answer_text": correct.answer_text if correct else None,
            "explanation": correct.explanation if correct else None,
            "time_spent_seconds": r.time_spent_seconds,
            "was_flagged": r.was_flagged,
            "skipped": r.selected_answer_id is None,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_available_questions(
        self,
        exam_id: int | None,
        filters: dict,
        question_ids: list[int] | None = None,
    ) -> list[Question]:
        """Fetch questions that are ready for practice, applying filters.

        Args:
            exam_id: Optional exam ID filter
            filters: Dict with optional keys: topic
            question_ids: Optional list of question IDs to restrict results to

        Returns:
            List of ready-for-practice questions
        """
        query = select(Question)

        if exam_id is not None:
            query = query.where(Question.exam_id == exam_id)

        if topic := filters.get("topic"):
            query = query.where(Question.topic == topic)

        if question_ids is not None:
            query = query.where(Question.id.in_(question_ids))

        result = await self.session.execute(query)
        all_questions = result.scalars().all()

        # is_ready_for_practice requires loaded answers (selectin on model)
        return [q for q in all_questions if q.is_ready_for_practice]

    async def _get_failed_question_ids(self, user_session_id: str) -> list[int]:
        """Return deduplicated IDs of questions this user has ever answered
        incorrectly.

        Joins ``PracticeResponse`` to ``PracticeSession`` on ``session_id``,
        filters by ``user_session_id`` and ``is_correct = False``, and
        returns the distinct ``question_id`` values.

        Args:
            user_session_id: Browser/user session identifier

        Returns:
            List of question IDs the user has answered incorrectly
        """
        result = await self.session.execute(
            select(PracticeResponse.question_id)
            .distinct()
            .join(PracticeSession, PracticeResponse.session_id == PracticeSession.id)
            .where(
                PracticeSession.user_session_id == user_session_id,
                PracticeResponse.is_correct == False,  # noqa: E712
            )
        )
        return list(result.scalars().all())
