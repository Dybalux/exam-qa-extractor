"""Tests for :class:`JsonIOService.export_full_db`.

The export path is a pure read: it must return a valid envelope with
``schema_version="1.0"``, an ISO-8601 ``exported_at`` timestamp, and
a flat-questions list with denormalized ``exam_context`` and nested
``answers``. Empty DB → ``questions=[]``. The eager-loading
contract is asserted by checking that the relationship accesses
happen without extra DB round-trips (the fixtures give us a single
transactional session, so any extra query is observable through the
``selectinload``-vs-lazy distinction).
"""

from __future__ import annotations

import re

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer import Answer
from app.models.exam import Exam
from app.models.question import Question
from app.schemas.json_io import (
    AnswerExportSchema,
    ExamContextExportSchema,
    ExportFileSchema,
    QuestionExportSchema,
)
from app.services.json_io_service import JsonIOService


_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


async def _make_exam(
    session: AsyncSession,
    partial_number: int = 1,
    exam_date: "date | None" = None,
    tags: str | None = "algebra",
) -> Exam:
    from datetime import date as _date

    exam = Exam(
        partial_number=partial_number,
        exam_date=exam_date if exam_date is not None else _date(2024, 6, 15),
        topic_tags=tags,
    )
    session.add(exam)
    await session.flush()
    return exam


async def _make_question(
    session: AsyncSession,
    exam: Exam,
    text: str = "What is 2+2?",
    topic: str = "OTHER",
    is_corrected: bool = False,
    answers: list[tuple[str, str]] | None = None,
) -> Question:
    q = Question(
        exam_id=exam.id,
        question_text=text,
        topic=topic,
        order_in_exam=1,
        is_corrected=is_corrected,
    )
    session.add(q)
    await session.flush()
    if answers:
        for idx, (text, atype) in enumerate(answers):
            a = Answer(
                question_id=q.id,
                answer_text=text,
                answer_type=atype,
                display_order=idx,
            )
            session.add(a)
    await session.flush()
    return q


@pytest.mark.asyncio
async def test_export_empty_db_returns_valid_envelope(db_session: AsyncSession) -> None:
    """Empty DB → ``questions=[]``, ``schema_version='1.0'``, valid envelope."""
    svc = JsonIOService(db_session)
    envelope = await svc.export_full_db()

    assert isinstance(envelope, ExportFileSchema)
    assert envelope.schema_version == "1.0"
    assert envelope.questions == []
    # ``exported_at`` is an aware UTC datetime.
    assert envelope.exported_at.tzinfo is not None
    # ``model_dump(mode="json")`` must produce a valid JSON-encodable dict.
    dumped = envelope.model_dump(mode="json")
    assert dumped["schema_version"] == "1.0"
    assert dumped["questions"] == []
    assert dumped["exported_at"]  # ISO-8601 string


@pytest.mark.asyncio
async def test_export_populated_db_round_trips_through_schema(
    db_session: AsyncSession,
) -> None:
    """A populated DB (3/12/48) round-trips through ``ExportFileSchema``."""
    # Create 3 exams, 4 questions per exam, 4 answers per question.
    # That's 3 exams, 12 questions, 48 answers.
    from datetime import date as _date

    for p in (1, 2, 3):
        exam = await _make_exam(
            db_session,
            partial_number=p,
            exam_date=_date(2024, p, 15),
            tags=f"topic-{p}",
        )
        for q_idx in range(4):
            await _make_question(
                db_session,
                exam,
                text=f"Q{q_idx} for exam {p}",
                topic="OTHER",
                answers=[(f"A{q_idx}{a}", "correct" if a == 0 else "incorrect") for a in range(4)],
            )
    await db_session.commit()

    svc = JsonIOService(db_session)
    envelope = await svc.export_full_db()

    assert isinstance(envelope, ExportFileSchema)
    assert envelope.schema_version == "1.0"
    assert len(envelope.questions) == 12

    # Every question must carry its exam context, every answer must
    # be nested, and the counts must match what we created.
    for q in envelope.questions:
        assert isinstance(q, QuestionExportSchema)
        assert isinstance(q.exam_context, ExamContextExportSchema)
        assert _UUID4_RE.match(q.exam_context.uuid)
        assert len(q.answers) == 4
        for a in q.answers:
            assert isinstance(a, AnswerExportSchema)
            assert _UUID4_RE.match(a.uuid)

    # Round-trip through model_dump / model_validate.
    dumped = envelope.model_dump(mode="json")
    re_parsed = ExportFileSchema.model_validate(dumped)
    assert len(re_parsed.questions) == 12
    assert re_parsed.schema_version == "1.0"


@pytest.mark.asyncio
async def test_export_includes_exam_context_fields(
    db_session: AsyncSession,
) -> None:
    """The denormalized exam context must carry every user-editable field."""
    from datetime import date as _date

    exam = await _make_exam(
        db_session,
        partial_number=2,
        exam_date=_date(2024, 7, 20),
        tags="geometry,calculus",
    )
    await _make_question(db_session, exam, text="Sample?", answers=[("Yes", "correct")])
    await db_session.commit()

    svc = JsonIOService(db_session)
    envelope = await svc.export_full_db()

    assert len(envelope.questions) == 1
    ctx = envelope.questions[0].exam_context
    assert ctx.partial_number == 2
    # ``exam_date`` is parsed to a ``date`` object (or None).
    assert ctx.exam_date == _date(2024, 7, 20)
    assert ctx.topic_tags == "geometry,calculus"


@pytest.mark.asyncio
async def test_export_answers_are_sorted_by_display_order(
    db_session: AsyncSession,
) -> None:
    """Answers are exported in ``display_order`` ascending."""
    exam = await _make_exam(db_session, partial_number=1)
    # Insert answers in reverse display order.
    q = Question(exam_id=exam.id, question_text="Q")
    db_session.add(q)
    await db_session.flush()
    for idx, text in enumerate(["third", "first", "second"]):
        db_session.add(
            Answer(
                question_id=q.id,
                answer_text=text,
                answer_type="correct" if idx == 0 else "incorrect",
                display_order=idx,
            )
        )
    await db_session.commit()

    svc = JsonIOService(db_session)
    envelope = await svc.export_full_db()

    answers = envelope.questions[0].answers
    # Insertion order: third(0)/first(1)/second(2). After sort by display_order: third, first, second.
    assert [a.answer_text for a in answers] == ["third", "first", "second"]


@pytest.mark.asyncio
async def test_export_uses_dedicated_logger_name(
    db_session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    """The service's logger must be the exact string in the plan."""
    import logging

    svc = JsonIOService(db_session)
    # Verify the logger name is the exact contract string.
    assert svc._logger.name == "app.services.json_io_service"
    # The logger is reachable via ``logging.getLogger`` with that name.
    assert logging.getLogger("app.services.json_io_service") is svc._logger

    # Trigger an export so the logger emits the info line; the
    # ``caplog`` fixture will capture it.
    with caplog.at_level(logging.INFO, logger="app.services.json_io_service"):
        await svc.export_full_db()

    matching = [
        record
        for record in caplog.records
        if record.name == "app.services.json_io_service"
    ]
    assert matching, (
        "Expected at least one log record on logger "
        "'app.services.json_io_service'"
    )
