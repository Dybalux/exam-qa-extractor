"""Practice Service for managing interactive study sessions."""

import logging
import random
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import (
    EXAM_SIMULATION_BLUEPRINTS,
    AnswerType,
    PracticeMode,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.models.answer import Answer
from app.models.exam import Exam
from app.models.practice_response import PracticeResponse
from app.models.practice_session import PracticeSession
from app.models.question import Question
from app.models.topic import Topic

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
        review_question_ids: list[int] | None = None,
    ) -> PracticeSession:
        """Create a new practice session.

        Args:
            user_session_id: Browser/user session identifier
            mode: Practice mode (random, by_partial, by_topic, exam_simulation)
            exam_id: Optional exam to restrict questions
            filters: Optional dict with keys: topic
            total_questions: Number of questions for this session (1-100)
            review_question_ids: error_review only. Review exactly these
                questions instead of every historical mistake.

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
            if review_question_ids:
                question_ids = list(review_question_ids)
            else:
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

        session_filters = dict(filters) if filters else {}
        if mode == PracticeMode.ERROR_REVIEW.value and review_question_ids:
            # Pin the pool so next_question keeps reviewing this exact set.
            session_filters["question_ids"] = [q.id for q in available]
        if mode == PracticeMode.EXAM_SIMULATION.value:
            blueprint = None
            if exam_id is not None:
                exam_stmt = select(Exam.partial_number).where(Exam.id == exam_id)
                exam_part = (await self.session.execute(exam_stmt)).scalar_one_or_none()
                if exam_part in EXAM_SIMULATION_BLUEPRINTS:
                    blueprint = EXAM_SIMULATION_BLUEPRINTS[exam_part]

            if blueprint is None:
                available_topics = {q.topic for q in available}
                if set(EXAM_SIMULATION_BLUEPRINTS[3].keys()).issubset(available_topics):
                    blueprint = EXAM_SIMULATION_BLUEPRINTS[3]

            if blueprint:
                selected_sample = self._select_structured_exam_questions(
                    available=available,
                    total=actual_total,
                    blueprint=blueprint,
                )
            else:
                selected_sample = random.sample(available, actual_total)

            session_filters["question_ids"] = [q.id for q in selected_sample]

        practice_session = PracticeSession(
            user_session_id=user_session_id,
            mode=mode,
            exam_id=exam_id,
            filters=session_filters,
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

    async def complete_session(
        self,
        session_id: int,
        lockout_reason: str | None = None,
    ) -> PracticeSession:
        """Mark a practice session as completed.

        Args:
            session_id: Session ID
            lockout_reason: Optional reason if session was terminated due to anti-cheat lockout

        Returns:
            Updated session

        Raises:
            NotFoundError: If session not found
            ValidationError: If session already completed
        """
        practice_session = await self.get_session(session_id)

        if practice_session.is_completed:
            if lockout_reason:
                curr_filters = dict(practice_session.filters or {})
                anti_cheat = dict(curr_filters.get("anti_cheat") or {})
                anti_cheat["locked_out"] = True
                anti_cheat["lockout_reason"] = lockout_reason
                curr_filters["anti_cheat"] = anti_cheat
                practice_session.filters = curr_filters
                await self.session.commit()
                await self.session.refresh(practice_session)
                return practice_session
            raise ValidationError(f"Session {session_id} is already completed")

        now = datetime.now(timezone.utc)
        practice_session.completed_at = now

        started_at = practice_session.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)

        elapsed = now - started_at
        practice_session.total_time_seconds = int(elapsed.total_seconds())

        if lockout_reason:
            curr_filters = dict(practice_session.filters or {})
            anti_cheat = dict(curr_filters.get("anti_cheat") or {})
            anti_cheat["locked_out"] = True
            anti_cheat["lockout_reason"] = lockout_reason
            curr_filters["anti_cheat"] = anti_cheat
            practice_session.filters = curr_filters

        await self.session.commit()
        await self.session.refresh(practice_session)

        logger.info(
            f"Completed session {session_id} "
            f"(accuracy={practice_session.accuracy:.1f}%, "
            f"time={practice_session.total_time_seconds}s, "
            f"lockout={lockout_reason})"
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

        # For error_review mode, recompute failed question IDs.
        # For exam_simulation, restrict to the preselected blueprint question IDs.
        question_ids = None
        if practice_session.mode == PracticeMode.ERROR_REVIEW.value:
            pinned = (practice_session.filters or {}).get("question_ids")
            question_ids = (
                pinned
                if pinned is not None
                else await self._get_failed_question_ids(
                    practice_session.user_session_id
                )
            )
        elif practice_session.mode == PracticeMode.EXAM_SIMULATION.value:
            question_ids = (practice_session.filters or {}).get("question_ids")

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
        existing_response = existing.scalar_one_or_none()
        if existing_response:
            if practice_session.mode == PracticeMode.EXAM_SIMULATION.value:
                # In exam simulation, user can navigate back and change/set their answer
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

                if existing_response.selected_answer_id is None:
                    practice_session.skipped_count = max(
                        0, practice_session.skipped_count - 1
                    )
                elif existing_response.is_correct:
                    practice_session.correct_count = max(
                        0, practice_session.correct_count - 1
                    )
                else:
                    practice_session.incorrect_count = max(
                        0, practice_session.incorrect_count - 1
                    )

                existing_response.selected_answer_id = selected_answer_id
                existing_response.is_correct = is_correct
                existing_response.time_spent_seconds += max(0, time_spent_seconds)
                existing_response.was_flagged = was_flagged
                existing_response.answered_at = datetime.now(timezone.utc)

                if is_correct:
                    practice_session.correct_count += 1
                else:
                    practice_session.incorrect_count += 1

                await self.session.commit()
                await self.session.refresh(existing_response)
                return existing_response
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
        existing_resp = existing.scalar_one_or_none()
        if existing_resp:
            if practice_session.mode == PracticeMode.EXAM_SIMULATION.value:
                return existing_resp
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

    async def get_exam_paper(self, session_id: int) -> dict:
        """Fetch all questions for an exam simulation session with user responses."""
        session = await self.get_session(session_id)

        question_ids = (session.filters or {}).get("question_ids")
        if not question_ids:
            available = await self._get_available_questions(
                exam_id=session.exam_id,
                filters=session.filters or {},
            )
            question_ids = [q.id for q in available[: session.total_questions]]
            if not session.filters:
                session.filters = {}
            session.filters["question_ids"] = question_ids
            await self.session.commit()

        q_res = await self.session.execute(
            select(Question)
            .options(selectinload(Question.answers))
            .where(Question.id.in_(question_ids))
        )
        q_map = {q.id: q for q in q_res.scalars().all()}
        ordered_questions = [q_map[qid] for qid in question_ids if qid in q_map]

        resp_res = await self.session.execute(
            select(PracticeResponse).where(PracticeResponse.session_id == session_id)
        )
        resp_map = {r.question_id: r for r in resp_res.scalars().all()}

        questions_data = []
        for q in ordered_questions:
            resp = resp_map.get(q.id)
            answers = list(q.answers)
            r_inst = random.Random(f"{session_id}_{q.id}")
            r_inst.shuffle(answers)
            questions_data.append(
                {
                    "id": q.id,
                    "text": q.question_text,
                    "topic": q.topic,
                    "answers": [{"id": a.id, "text": a.answer_text} for a in answers],
                    "selected_answer_id": resp.selected_answer_id if resp else None,
                }
            )

        return {
            "session": session,
            "questions": questions_data,
        }

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

        anti_cheat = (practice_session.filters or {}).get("anti_cheat") or {}
        lockout_reason = (
            anti_cheat.get("lockout_reason") if anti_cheat.get("locked_out") else None
        )

        blueprint_ids = (
            (practice_session.filters or {}).get("question_ids")
            if practice_session.mode == PracticeMode.EXAM_SIMULATION.value
            else None
        )

        if blueprint_ids is not None:
            total_questions = (
                len(blueprint_ids)
                if blueprint_ids
                else practice_session.total_questions
            )
            q_res = await self.session.execute(
                select(Question)
                .options(selectinload(Question.answers))
                .where(Question.id.in_(blueprint_ids))
            )
            q_map = {q.id: q for q in q_res.scalars().all()}
            resp_map = {r.question_id: r for r in responses}

            responses_detail = []
            answered_count = 0
            for qid in blueprint_ids:
                if qid in resp_map:
                    r = resp_map[qid]
                    detail = self._build_response_detail(r)
                    if r.selected_answer_id is not None:
                        answered_count += 1
                    responses_detail.append(detail)
                elif qid in q_map:
                    q = q_map[qid]
                    correct = q.correct_answer
                    responses_detail.append(
                        {
                            "question_id": q.id,
                            "question_text": q.question_text,
                            "selected_answer_id": None,
                            "selected_answer_text": None,
                            "is_correct": False,
                            "correct_answer_text": correct.answer_text
                            if correct
                            else None,
                            "explanation": correct.explanation if correct else None,
                            "time_spent_seconds": 0,
                            "was_flagged": False,
                            "skipped": True,
                            "is_skipped": True,
                        }
                    )

            skipped_count = max(0, total_questions - answered_count)
            accuracy = (
                (practice_session.correct_count / total_questions * 100.0)
                if total_questions > 0
                else 0.0
            )

            return {
                "session_id": session_id,
                "mode": practice_session.mode,
                "is_completed": practice_session.is_completed,
                "total_questions": total_questions,
                "questions_answered": answered_count,
                "correct_count": practice_session.correct_count,
                "incorrect_count": practice_session.incorrect_count,
                "skipped_count": skipped_count,
                "accuracy": accuracy,
                "total_time_seconds": practice_session.total_time_seconds,
                "lockout_reason": lockout_reason,
                "responses": responses_detail,
            }

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
            "lockout_reason": lockout_reason,
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
            "is_skipped": r.selected_answer_id is None,
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
        query = select(Question).options(selectinload(Question.topic_relation))

        if exam_id is not None:
            query = query.where(Question.exam_id == exam_id)

        if topic := filters.get("topic"):
            query = query.join(Topic, Question.topic_id == Topic.id).where(
                Topic.slug == topic
            )

        if question_ids is not None:
            query = query.where(Question.id.in_(question_ids))

        result = await self.session.execute(query)
        all_questions = result.scalars().all()

        # is_ready_for_practice requires loaded answers (selectin on model)
        return [q for q in all_questions if q.is_ready_for_practice]

    def _select_structured_exam_questions(
        self,
        available: list[Question],
        total: int,
        blueprint: dict[str, float],
    ) -> list[Question]:
        """Select questions according to a topic distribution blueprint with fallback.

        Args:
            available: Pool of questions ready for practice
            total: Desired total number of questions
            blueprint: Dict mapping topic slug -> target percentage (e.g. 0.30)

        Returns:
            List of selected Question instances
        """
        if not available:
            return []

        actual_total = min(total, len(available))
        if actual_total <= 0:
            return []

        # Group available questions by topic slug
        pool_by_topic: dict[str, list[Question]] = defaultdict(list)
        for q in available:
            pool_by_topic[q.topic].append(q)

        # Calculate integer quota per topic
        quotas: dict[str, int] = {}
        allocated = 0
        for topic, weight in blueprint.items():
            quota = round(actual_total * weight)
            quotas[topic] = quota
            allocated += quota

        # Reconcile rounding discrepancies
        if allocated != actual_total and quotas:
            diff = actual_total - allocated
            sorted_topics = sorted(
                blueprint.keys(), key=lambda t: blueprint[t], reverse=True
            )
            for t in sorted_topics:
                if diff == 0:
                    break
                if diff > 0:
                    quotas[t] += 1
                    diff -= 1
                elif diff < 0 and quotas[t] > 0:
                    quotas[t] -= 1
                    diff += 1

        selected: list[Question] = []
        selected_ids: set[int] = set()

        # Step 1: Draw up to quota for each topic in blueprint
        for topic, quota in quotas.items():
            topic_pool = [
                q for q in pool_by_topic.get(topic, []) if q.id not in selected_ids
            ]
            take_count = min(quota, len(topic_pool))
            if take_count > 0:
                sampled = random.sample(topic_pool, take_count)
                selected.extend(sampled)
                selected_ids.update(q.id for q in sampled)

        # Step 2: Fallback if any topic lacked sufficient questions
        if len(selected) < actual_total:
            remaining_pool = [q for q in available if q.id not in selected_ids]
            needed = actual_total - len(selected)
            if remaining_pool and needed > 0:
                fallback_sample = random.sample(
                    remaining_pool, min(needed, len(remaining_pool))
                )
                selected.extend(fallback_sample)
                selected_ids.update(q.id for q in fallback_sample)

        # Step 3: Ensure exact target size
        selected = selected[:actual_total]

        # Step 4: Randomize question order across chapters
        random.shuffle(selected)
        return selected

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
