"""Analytics Service for study progress and performance tracking."""

import logging
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam import Exam
from app.models.practice_response import PracticeResponse
from app.models.practice_session import PracticeSession
from app.models.question import Question

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for study analytics and progress tracking."""

    def __init__(self, session: AsyncSession):
        """Initialize analytics service.

        Args:
            session: Database session
        """
        self.session = session

    async def get_overall_stats(self) -> dict:
        """Get system-wide statistics.

        Returns:
            Dict with total counts for exams, questions, answers, and sessions
        """
        total_exams = await self.session.scalar(select(func.count(Exam.id)))
        total_questions = await self.session.scalar(select(func.count(Question.id)))
        total_sessions = await self.session.scalar(
            select(func.count(PracticeSession.id))
        )
        completed_sessions = await self.session.scalar(
            select(func.count(PracticeSession.id)).where(
                PracticeSession.completed_at != None  # noqa: E711
            )
        )

        # Questions ready for practice (have a correct answer)
        all_questions_result = await self.session.execute(select(Question))
        all_questions = all_questions_result.scalars().all()
        ready_count = sum(1 for q in all_questions if q.is_ready_for_practice)
        corrected_count = sum(1 for q in all_questions if q.is_corrected)

        stats = {
            "total_exams": total_exams or 0,
            "total_questions": total_questions or 0,
            "questions_ready_for_practice": ready_count,
            "questions_corrected": corrected_count,
            "practice_readiness_pct": (
                round(ready_count / total_questions * 100, 1)
                if total_questions
                else 0.0
            ),
            "total_practice_sessions": total_sessions or 0,
            "completed_practice_sessions": completed_sessions or 0,
        }

        logger.info("Generated overall stats")
        return stats

    async def get_topic_performance(self, user_session_id: str) -> dict:
        """Get accuracy breakdown by topic for a specific user.

        Args:
            user_session_id: Browser/user session identifier

        Returns:
            Dict mapping topic → {correct, total, accuracy_pct}
        """
        # Get all completed responses for this user
        sessions_result = await self.session.execute(
            select(PracticeSession.id).where(
                PracticeSession.user_session_id == user_session_id
            )
        )
        session_ids = list(sessions_result.scalars().all())

        if not session_ids:
            return {}

        responses_result = await self.session.execute(
            select(PracticeResponse).where(
                PracticeResponse.session_id.in_(session_ids),
                PracticeResponse.is_correct != None,  # noqa: E711
            )
        )
        responses = responses_result.scalars().all()

        if not responses:
            return {}

        # Load questions to get topics
        question_ids = {r.question_id for r in responses}
        questions_result = await self.session.execute(
            select(Question).where(Question.id.in_(question_ids))
        )
        topic_by_question = {q.id: q.topic for q in questions_result.scalars().all()}

        # Aggregate by topic
        totals: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0})
        for response in responses:
            topic = topic_by_question.get(response.question_id, "other")
            totals[topic]["total"] += 1
            if response.is_correct:
                totals[topic]["correct"] += 1

        return {
            topic: {
                "correct": data["correct"],
                "total": data["total"],
                "accuracy_pct": round(data["correct"] / data["total"] * 100, 1),
            }
            for topic, data in sorted(totals.items())
        }

    async def get_weak_areas(
        self,
        user_session_id: str,
        threshold_pct: float = 60.0,
    ) -> list[dict]:
        """Identify topics where the user performs below the threshold.

        Args:
            user_session_id: Browser/user session identifier
            threshold_pct: Accuracy percentage below which a topic is "weak"

        Returns:
            List of dicts {topic, accuracy_pct, correct, total},
            ordered by accuracy ascending (weakest first)
        """
        performance = await self.get_topic_performance(user_session_id)

        weak = [
            {"topic": topic, **data}
            for topic, data in performance.items()
            if data["accuracy_pct"] < threshold_pct
        ]

        weak.sort(key=lambda x: x["accuracy_pct"])

        logger.info(
            f"User {user_session_id[:8]}...: {len(weak)} weak areas "
            f"(threshold={threshold_pct}%)"
        )
        return weak

    async def get_session_history(
        self,
        user_session_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """Get recent practice sessions for a user.

        Args:
            user_session_id: Browser/user session identifier
            limit: Maximum sessions to return

        Returns:
            List of session summary dicts, most recent first
        """
        result = await self.session.execute(
            select(PracticeSession)
            .where(PracticeSession.user_session_id == user_session_id)
            .order_by(PracticeSession.started_at.desc())
            .limit(limit)
        )
        sessions = result.scalars().all()

        return [
            {
                "session_id": s.id,
                "mode": s.mode,
                "is_completed": s.is_completed,
                "total_questions": s.total_questions,
                "questions_answered": s.questions_answered,
                "correct_count": s.correct_count,
                "accuracy_pct": round(s.accuracy, 1),
                "total_time_seconds": s.total_time_seconds,
                "started_at": s.started_at.isoformat(),
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            }
            for s in sessions
        ]

    async def get_study_progress(self) -> dict:
        """Get a high-level view of content readiness by partial and topic.

        Returns:
            Dict with readiness breakdown by partial number and by topic
        """
        exams_result = await self.session.execute(select(Exam))
        exams = exams_result.scalars().all()

        questions_result = await self.session.execute(select(Question))
        questions = questions_result.scalars().all()

        # By partial number
        by_partial: dict[int, dict] = defaultdict(lambda: {"total": 0, "ready": 0})
        exam_to_partial = {e.id: e.partial_number for e in exams}

        for q in questions:
            partial = exam_to_partial.get(q.exam_id, 0)
            by_partial[partial]["total"] += 1
            if q.is_ready_for_practice:
                by_partial[partial]["ready"] += 1

        # By topic
        by_topic: dict[str, dict] = defaultdict(lambda: {"total": 0, "ready": 0})
        for q in questions:
            by_topic[q.topic]["total"] += 1
            if q.is_ready_for_practice:
                by_topic[q.topic]["ready"] += 1

        def pct(ready: int, total: int) -> float:
            return round(ready / total * 100, 1) if total else 0.0

        return {
            "by_partial": {
                partial: {
                    "total": data["total"],
                    "ready": data["ready"],
                    "readiness_pct": pct(data["ready"], data["total"]),
                }
                for partial, data in sorted(by_partial.items())
            },
            "by_topic": {
                topic: {
                    "total": data["total"],
                    "ready": data["ready"],
                    "readiness_pct": pct(data["ready"], data["total"]),
                }
                for topic, data in sorted(by_topic.items())
            },
        }

    async def get_exam_coverage(self, exam_id: int) -> dict:
        """Get question coverage statistics for a specific exam.

        Args:
            exam_id: Exam ID

        Returns:
            Dict with per-topic breakdown and overall readiness

        Raises:
            ValueError: If no questions found for the exam
        """
        questions_result = await self.session.execute(
            select(Question).where(Question.exam_id == exam_id)
        )
        questions = list(questions_result.scalars().all())

        if not questions:
            return {
                "exam_id": exam_id,
                "total_questions": 0,
                "by_topic": {},
            }

        by_topic: dict[str, dict] = defaultdict(
            lambda: {"total": 0, "ready": 0, "corrected": 0}
        )

        for q in questions:
            by_topic[q.topic]["total"] += 1
            if q.is_ready_for_practice:
                by_topic[q.topic]["ready"] += 1
            if q.is_corrected:
                by_topic[q.topic]["corrected"] += 1

        total = len(questions)
        ready = sum(1 for q in questions if q.is_ready_for_practice)
        corrected = sum(1 for q in questions if q.is_corrected)

        return {
            "exam_id": exam_id,
            "total_questions": total,
            "ready_for_practice": ready,
            "corrected": corrected,
            "readiness_pct": round(ready / total * 100, 1) if total else 0.0,
            "correction_pct": round(corrected / total * 100, 1) if total else 0.0,
            "by_topic": {
                topic: {
                    "total": data["total"],
                    "ready": data["ready"],
                    "corrected": data["corrected"],
                    "readiness_pct": round(data["ready"] / data["total"] * 100, 1),
                }
                for topic, data in sorted(by_topic.items())
            },
        }
