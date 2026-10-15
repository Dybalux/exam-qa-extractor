"""Unit tests for PracticeService exam_simulation structured chapter quotas."""

from collections import Counter

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import AnswerType, PracticeMode
from app.models.answer import Answer
from app.models.exam import Exam
from app.models.question import Question
from app.models.topic import Topic
from app.services.practice_service import PracticeService


async def _create_topic_with_questions(
    db_session: AsyncSession,
    exam_id: int,
    subject_id: int,
    topic_slug: str,
    count: int,
) -> Topic:
    """Helper to get or create topic and populate questions with valid answers."""
    result = await db_session.execute(
        select(Topic).where(Topic.slug == topic_slug, Topic.subject_id == subject_id)
    )
    topic = result.scalar_one_or_none()
    if not topic:
        topic = Topic(name=topic_slug.title(), slug=topic_slug, subject_id=subject_id)
        db_session.add(topic)
        await db_session.flush()

    for i in range(count):
        q = Question(
            exam_id=exam_id,
            question_text=f"Question {i} for {topic_slug}?",
            topic_id=topic.id,
            is_corrected=True,
        )
        db_session.add(q)
        await db_session.flush()

        ans = Answer(
            question_id=q.id,
            answer_text="Correct answer",
            answer_type=AnswerType.CORRECT.value,
            display_order=0,
        )
        db_session.add(ans)

    await db_session.flush()
    return topic


@pytest.mark.asyncio
async def test_simulation_selects_exact_chapter_quotas(
    db_session: AsyncSession,
    default_subject,
) -> None:
    """A 10-question exam_simulation for Parcial 3 must select exactly:
    1 processes, 3 scheduling, 3 synchronization, 2 deadlock, 1 memory.
    """
    service = PracticeService(db_session)
    exam = Exam(partial_number=3, subject_id=default_subject.id)
    db_session.add(exam)
    await db_session.flush()

    # Seed 5 questions for each topic (more than enough for the 10-question quotas)
    await _create_topic_with_questions(
        db_session, exam.id, default_subject.id, "processes", 5
    )
    await _create_topic_with_questions(
        db_session, exam.id, default_subject.id, "scheduling", 5
    )
    await _create_topic_with_questions(
        db_session, exam.id, default_subject.id, "synchronization", 5
    )
    await _create_topic_with_questions(
        db_session, exam.id, default_subject.id, "deadlock", 5
    )
    await _create_topic_with_questions(
        db_session, exam.id, default_subject.id, "memory", 5
    )
    await db_session.commit()

    session = await service.create_session(
        user_session_id="test-sim-quotas",
        mode=PracticeMode.EXAM_SIMULATION.value,
        exam_id=exam.id,
        total_questions=10,
    )

    question_ids = session.filters.get("question_ids")
    assert question_ids is not None
    assert len(question_ids) == 10

    # Query selected questions to check topic distribution
    q_res = await db_session.execute(
        select(Question)
        .options(selectinload(Question.topic_relation))
        .where(Question.id.in_(question_ids))
    )
    selected_questions = q_res.scalars().all()
    topic_counts = Counter(q.topic for q in selected_questions)

    assert topic_counts["processes"] == 1
    assert topic_counts["scheduling"] == 3
    assert topic_counts["synchronization"] == 3
    assert topic_counts["deadlock"] == 2
    assert topic_counts["memory"] == 1


@pytest.mark.asyncio
async def test_simulation_fallback_when_topic_has_insufficient_questions(
    db_session: AsyncSession,
    default_subject,
) -> None:
    """When a topic has fewer questions than its quota (e.g. 0 memory questions),
    the selection must gracefully fall back to drawing the missing questions
    from remaining available questions to complete the 10-question total.
    """
    service = PracticeService(db_session)
    exam = Exam(partial_number=3, subject_id=default_subject.id)
    db_session.add(exam)
    await db_session.flush()

    # Seed topics but omit 'memory' questions completely
    await _create_topic_with_questions(
        db_session, exam.id, default_subject.id, "processes", 5
    )
    await _create_topic_with_questions(
        db_session, exam.id, default_subject.id, "scheduling", 5
    )
    await _create_topic_with_questions(
        db_session, exam.id, default_subject.id, "synchronization", 5
    )
    await _create_topic_with_questions(
        db_session, exam.id, default_subject.id, "deadlock", 5
    )
    # memory has 0 questions!
    await db_session.commit()

    session = await service.create_session(
        user_session_id="test-sim-fallback",
        mode=PracticeMode.EXAM_SIMULATION.value,
        exam_id=exam.id,
        total_questions=10,
    )

    question_ids = session.filters.get("question_ids")
    assert question_ids is not None
    assert len(question_ids) == 10

    q_res = await db_session.execute(
        select(Question)
        .options(selectinload(Question.topic_relation))
        .where(Question.id.in_(question_ids))
    )
    selected_questions = q_res.scalars().all()
    assert len(selected_questions) == 10

    topic_counts = Counter(q.topic for q in selected_questions)
    assert topic_counts["memory"] == 0
    # The 1 missing question was covered by other topics
    assert sum(topic_counts.values()) == 10


@pytest.mark.asyncio
async def test_simulation_uniform_fallback_when_no_blueprint_matches(
    db_session: AsyncSession,
    default_subject,
) -> None:
    """When an exam belongs to a partial number without a configured blueprint,
    it falls back to uniform random sampling.
    """
    service = PracticeService(db_session)
    # Parcial 1 does not have a blueprint in EXAM_SIMULATION_BLUEPRINTS
    exam = Exam(partial_number=1, subject_id=default_subject.id)
    db_session.add(exam)
    await db_session.flush()

    await _create_topic_with_questions(
        db_session, exam.id, default_subject.id, "files", 6
    )
    await _create_topic_with_questions(db_session, exam.id, default_subject.id, "io", 6)
    await db_session.commit()

    session = await service.create_session(
        user_session_id="test-sim-no-blueprint",
        mode=PracticeMode.EXAM_SIMULATION.value,
        exam_id=exam.id,
        total_questions=5,
    )

    question_ids = session.filters.get("question_ids")
    assert question_ids is not None
    assert len(question_ids) == 5
