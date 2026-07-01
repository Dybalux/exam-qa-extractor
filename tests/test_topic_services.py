"""Integration tests for topic-aware services (QuestionService, SearchService, JsonIOService).

These tests verify that the services correctly resolve dynamic Topic
records instead of using the deprecated TopicEnum.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.models.exam import Exam
from app.models.question import Question
from app.models.subject import Subject
from app.models.topic import Topic
from app.schemas.json_io import (
    ExamContextExportSchema,
    ExportFileSchema,
    QuestionExportSchema,
)
from app.services.json_io_service import JsonIOService
from app.services.question_service import QuestionService
from app.services.search_service import SearchService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_subject_and_topics(session: AsyncSession) -> Subject:
    """Create a default Subject and a few Topics for testing."""
    subject = Subject(name="Sistemas Operativos", slug="sistemas-operativos")
    session.add(subject)
    await session.flush()

    topics_data = [
        ("processes", "Procesos"),
        ("memory", "Memoria"),
        ("other", "Otros"),
    ]
    for slug, name in topics_data:
        session.add(Topic(name=name, slug=slug, subject_id=subject.id))
    await session.flush()
    return subject


async def _make_exam(session: AsyncSession, subject: Subject) -> Exam:
    """Create a minimal exam linked to the given subject."""
    exam = Exam(partial_number=1, subject_id=subject.id)
    session.add(exam)
    await session.flush()
    return exam


# ---------------------------------------------------------------------------
# QuestionService tests (REQ-QEXT-1: dynamic topic resolution)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_question_service_create_resolves_topic_by_slug(
    db_session: AsyncSession,
) -> None:
    """Creating a question with a valid topic slug sets topic_id correctly."""
    subject = await _seed_subject_and_topics(db_session)
    exam = await _make_exam(db_session, subject)
    svc = QuestionService(db_session)

    q = await svc.create_question(
        exam_id=exam.id,
        question_text="Explicar qué es un proceso.",
        topic="processes",
    )

    assert q.topic_id is not None
    assert q.topic == "processes"
    assert q.topic_relation is not None
    assert q.topic_relation.slug == "processes"


@pytest.mark.asyncio
async def test_question_service_create_rejects_unknown_topic(
    db_session: AsyncSession,
) -> None:
    """Creating a question with an unknown topic slug raises ValidationError."""
    subject = await _seed_subject_and_topics(db_session)
    exam = await _make_exam(db_session, subject)
    svc = QuestionService(db_session)

    with pytest.raises(ValidationError, match="Invalid topic"):
        await svc.create_question(
            exam_id=exam.id,
            question_text="Pregunta de ejemplo.",
            topic="nonexistent-topic",
        )


@pytest.mark.asyncio
async def test_question_service_update_topic(
    db_session: AsyncSession,
) -> None:
    """Updating a question's topic slug changes its topic_id."""
    subject = await _seed_subject_and_topics(db_session)
    exam = await _make_exam(db_session, subject)
    svc = QuestionService(db_session)

    q = await svc.create_question(
        exam_id=exam.id,
        question_text="Pregunta inicial.",
        topic="other",
    )
    assert q.topic == "other"

    updated = await svc.update_question(question_id=q.id, topic="memory")
    assert updated.topic == "memory"
    assert updated.topic_id is not None
    assert updated.topic_relation.slug == "memory"


@pytest.mark.asyncio
async def test_question_service_list_filter_by_topic_slug(
    db_session: AsyncSession,
) -> None:
    """List questions filtered by topic slug using join on topics table."""
    subject = await _seed_subject_and_topics(db_session)
    exam = await _make_exam(db_session, subject)
    svc = QuestionService(db_session)

    await svc.create_question(exam_id=exam.id, question_text="Q1", topic="processes")
    await svc.create_question(exam_id=exam.id, question_text="Q2", topic="memory")
    await svc.create_question(exam_id=exam.id, question_text="Q3", topic="processes")

    processes_qs = await svc.list_questions(exam_id=exam.id, topic="processes")
    assert len(processes_qs) == 2

    memory_qs = await svc.list_questions(exam_id=exam.id, topic="memory")
    assert len(memory_qs) == 1


# ---------------------------------------------------------------------------
# SearchService tests (REQ-QEXT-1: dynamic topic filtering in search)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_service_filters_by_topic_slug(
    db_session: AsyncSession,
) -> None:
    """Search results are filtered by topic slug via topics table join."""
    subject = await _seed_subject_and_topics(db_session)
    exam = await _make_exam(db_session, subject)
    qsvc = QuestionService(db_session)

    await qsvc.create_question(
        exam_id=exam.id, question_text="Procesos e hilos", topic="processes"
    )
    await qsvc.create_question(
        exam_id=exam.id, question_text="Memoria virtual", topic="memory"
    )

    search = SearchService(db_session)
    results = await search.search_questions(query="Procesos", topic="processes")
    assert len(results) == 1
    assert results[0].topic == "processes"

    # Search without topic filter should return both.
    all_results = await search.search_questions(query="virtual")
    assert len(all_results) == 1
    assert all_results[0].topic == "memory"


@pytest.mark.asyncio
async def test_search_by_topic_uses_dynamic_lookup(
    db_session: AsyncSession,
) -> None:
    """search_by_topic resolves topic slug dynamically, not via TopicEnum."""
    subject = await _seed_subject_and_topics(db_session)
    exam = await _make_exam(db_session, subject)
    qsvc = QuestionService(db_session)

    await qsvc.create_question(
        exam_id=exam.id, question_text="Q processes", topic="processes"
    )

    search = SearchService(db_session)
    results = await search.search_by_topic("processes")
    assert len(results) == 1

    # Unknown topic raises ValueError.
    with pytest.raises(ValueError, match="Invalid topic"):
        await search.search_by_topic("nonexistent")


@pytest.mark.asyncio
async def test_search_by_topic_unknown_raises_with_valid_list(
    db_session: AsyncSession,
) -> None:
    """Unknown topic slug raises ValueError listing valid slugs."""
    await _seed_subject_and_topics(db_session)
    search = SearchService(db_session)

    with pytest.raises(ValueError) as exc_info:
        await search.search_by_topic("fantasy-topic")
    assert "memory" in str(exc_info.value)
    assert "processes" in str(exc_info.value)


# ---------------------------------------------------------------------------
# JsonIOService tests (REQ-IMP-1, REQ-IMP-2: legacy import + dynamic topics)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_resolves_existing_topic_by_slug(
    db_session: AsyncSession,
) -> None:
    """Import maps legacy topic string to existing Topic record."""
    await _seed_subject_and_topics(db_session)
    await db_session.commit()  # close implicit transaction before apply_import

    svc = JsonIOService(db_session)
    envelope = ExportFileSchema(
        schema_version="1.0",
        exported_at="2026-06-30T00:00:00Z",
        questions=[
            QuestionExportSchema(
                uuid="a" * 32,
                exam_context=ExamContextExportSchema(
                    uuid="e" * 32, partial_number=1, exam_date=None, topic_tags=None
                ),
                question_text="Describe procesos.",
                topic="processes",
                order_in_exam=1,
                is_corrected=False,
                correction_notes=None,
                has_code_in_answers=False,
                image_id=None,
                confidence_score=None,
                extracted_text=None,
                answers=[],
            )
        ],
    )

    result = await svc.apply_import(envelope.model_dump(mode="json"))
    assert result.created >= 1

    # Verify the question got the correct topic_id.
    from sqlalchemy import select

    q_row = await db_session.execute(select(Question).where(Question.uuid == "a" * 32))
    question = q_row.scalar_one()
    assert question.topic_id is not None
    assert question.topic == "processes"


@pytest.mark.asyncio
async def test_import_creates_missing_topic_dynamically(
    db_session: AsyncSession,
) -> None:
    """Import dynamically creates unrecognized topics (REQ-IMP-2)."""
    await _seed_subject_and_topics(db_session)
    await db_session.commit()  # close implicit transaction before apply_import

    svc = JsonIOService(db_session)
    envelope = ExportFileSchema(
        schema_version="1.0",
        exported_at="2026-06-30T00:00:00Z",
        questions=[
            QuestionExportSchema(
                uuid="b" * 32,
                exam_context=ExamContextExportSchema(
                    uuid="f" * 32, partial_number=2, exam_date=None, topic_tags=None
                ),
                question_text="Describe virtual memory.",
                topic="virtual-memory",
                order_in_exam=1,
                is_corrected=False,
                correction_notes=None,
                has_code_in_answers=False,
                image_id=None,
                confidence_score=None,
                extracted_text=None,
                answers=[],
            )
        ],
    )

    result = await svc.apply_import(envelope.model_dump(mode="json"))
    assert result.created >= 1

    # Verify the topic was dynamically created.
    from sqlalchemy import select

    topic_row = await db_session.execute(
        select(Topic).where(Topic.slug == "virtual-memory")
    )
    topic = topic_row.scalar_one()
    assert topic.name == "virtual-memory"
    assert topic.slug == "virtual-memory"

    # Verify the question is linked to the new topic.
    q_row = await db_session.execute(select(Question).where(Question.uuid == "b" * 32))
    question = q_row.scalar_one()
    assert question.topic_id == topic.id


@pytest.mark.asyncio
async def test_export_includes_topic_slug(
    db_session: AsyncSession,
) -> None:
    """Export serializes the dynamic topic slug."""
    subject = await _seed_subject_and_topics(db_session)
    exam = await _make_exam(db_session, subject)
    qsvc = QuestionService(db_session)

    await qsvc.create_question(
        exam_id=exam.id, question_text="Test question", topic="memory"
    )

    svc = JsonIOService(db_session)
    envelope = await svc.export_full_db()

    assert len(envelope.questions) == 1
    assert envelope.questions[0].topic == "memory"


@pytest.mark.asyncio
async def test_bulk_create_resolves_topics(
    db_session: AsyncSession,
) -> None:
    """Bulk creation resolves topic slugs to topic_ids in bulk."""
    subject = await _seed_subject_and_topics(db_session)
    exam = await _make_exam(db_session, subject)
    svc = QuestionService(db_session)

    questions = await svc.bulk_create_from_ocr(
        exam_id=exam.id,
        questions_data=[
            {"question_text": "Q1", "topic": "processes"},
            {"question_text": "Q2", "topic": "memory"},
        ],
    )

    assert len(questions) == 2
    assert questions[0].topic == "processes"
    assert questions[1].topic == "memory"
    assert questions[0].topic_id is not None
    assert questions[1].topic_id is not None
    assert questions[0].topic_id != questions[1].topic_id
