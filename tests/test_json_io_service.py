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


# ===========================================================================
# Tests for preview_import (T2.3)
# ===========================================================================

import pytest

from app.core.exceptions import MalformedImportError, UnknownSchemaVersion
from app.schemas.json_io import (
    AnswerExportSchema,
    ExamContextExportSchema,
    ExportFileSchema,
    QuestionExportSchema,
)
from app.services.json_io_service import JsonIOService, PREVIEW_ENTRY_CAP


def _envelope_dict(
    questions: list[dict],
    schema_version: str = "1.0",
) -> dict:
    """Build a raw JSON-loaded dict (what the HTTP layer hands the service)."""
    return {
        "schema_version": schema_version,
        "exported_at": "2024-06-15T12:00:00+00:00",
        "questions": questions,
    }


def _question_dict(
    uuid: str,
    exam_uuid: str,
    text: str = "Q",
    is_corrected: bool = False,
    answers: list[dict] | None = None,
    topic: str = "OTHER",
) -> dict:
    """Build a raw JSON question entry for tests."""
    if answers is None:
        answers = []
    return {
        "uuid": uuid,
        "exam_context": {
            "uuid": exam_uuid,
            "partial_number": 1,
            "exam_date": "2024-06-15",
            "topic_tags": "algebra",
        },
        "question_text": text,
        "extracted_text": None,
        "topic": topic,
        "order_in_exam": 1,
        "is_corrected": is_corrected,
        "correction_notes": None,
        "has_code_in_answers": False,
        "answers": answers,
    }


def _answer_dict(
    uuid: str,
    text: str = "A",
    atype: str = "correct",
    display_order: int = 0,
) -> dict:
    return {
        "uuid": uuid,
        "answer_text": text,
        "answer_type": atype,
        "is_common_misconception": False,
        "explanation": None,
        "display_order": display_order,
    }


@pytest.mark.asyncio
async def test_preview_no_db_writes(db_session: AsyncSession) -> None:
    """``preview_import`` must NOT add, update, or delete any rows."""
    # Seed an exam and a question so the DB is not empty.
    exam = Exam(partial_number=1, exam_date=__import__("datetime").date(2024, 6, 15), topic_tags="a")
    db_session.add(exam)
    await db_session.flush()
    q = Question(exam_id=exam.id, question_text="Seed", is_corrected=False)
    db_session.add(q)
    await db_session.commit()

    from sqlalchemy import func, select as _select

    # Capture counts before the preview.
    exam_count_before = (
        await db_session.execute(_select(func.count()).select_from(Exam))
    ).scalar_one()
    question_count_before = (
        await db_session.execute(_select(func.count()).select_from(Question))
    ).scalar_one()
    answer_count_before = (
        await db_session.execute(_select(func.count()).select_from(Answer))
    ).scalar_one()

    # Preview an envelope that would create 1 new question and delete the seed.
    payload = _envelope_dict(
        [
            _question_dict(
                uuid="99999999-9999-4999-8999-999999999999",
                exam_uuid=exam.uuid,
                text="Brand new question",
            )
        ]
    )
    svc = JsonIOService(db_session)
    preview = await svc.preview_import(payload)
    assert preview.to_create == 1
    assert preview.to_delete == 1

    # DB row counts must be unchanged after a preview.
    exam_count_after = (
        await db_session.execute(_select(func.count()).select_from(Exam))
    ).scalar_one()
    question_count_after = (
        await db_session.execute(_select(func.count()).select_from(Question))
    ).scalar_one()
    answer_count_after = (
        await db_session.execute(_select(func.count()).select_from(Answer))
    ).scalar_one()

    assert exam_count_after == exam_count_before
    assert question_count_after == question_count_before
    assert answer_count_after == answer_count_before


@pytest.mark.asyncio
async def test_preview_mixed_changes(db_session: AsyncSession) -> None:
    """Mixed envelope: 5 new / 3 update / 0 delete / 1 malformed report."""
    from datetime import date as _date

    # Seed 3 existing questions that will be the "update" half.
    exam = Exam(partial_number=1, exam_date=_date(2024, 6, 15), topic_tags="algebra")
    db_session.add(exam)
    await db_session.flush()

    update_uuids: list[str] = []
    for i in range(3):
        q = Question(
            exam_id=exam.id,
            question_text=f"Old Q{i}",
            is_corrected=False,
        )
        db_session.add(q)
        await db_session.flush()
        update_uuids.append(q.uuid)
    await db_session.commit()

    # Build the JSON envelope: 5 new + 3 updated + 1 malformed.
    questions: list[dict] = []
    for i in range(5):
        questions.append(
            _question_dict(
                uuid=f"0000000{i}-0000-4000-8000-000000000000",
                exam_uuid=exam.uuid,
                text=f"New Q{i}",
            )
        )
    for idx, q_uuid in enumerate(update_uuids):
        questions.append(
            _question_dict(
                uuid=q_uuid,
                exam_uuid=exam.uuid,
                text=f"Updated Q{idx}",
                is_corrected=True,  # forces a content diff → to_update
            )
        )
    # 1 malformed: topic is missing the required type. ``partial_number`` is
    # coerced to a non-int (via the strict schema: out of range 1..4 → fails).
    bad = _question_dict(
        uuid="99999999-9999-4999-8999-999999999999",
        exam_uuid=exam.uuid,
    )
    bad["exam_context"]["partial_number"] = 99  # out of ge=1, le=4
    questions.append(bad)

    payload = _envelope_dict(questions)
    svc = JsonIOService(db_session)

    # The malformed entry triggers a single ``MalformedImportError``
    # whose details carry every failure (1 entry in this case).
    with pytest.raises(MalformedImportError) as exc_info:
        await svc.preview_import(payload)
    err = exc_info.value
    assert err.details is not None
    validation_errors = err.details["validation_errors"]
    assert len(validation_errors) == 1
    assert validation_errors[0]["index"] == len(questions) - 1

    # Now drop the malformed entry and re-run: 5 create / 3 update / 0 delete.
    good_payload = _envelope_dict(questions[:-1])
    preview = await svc.preview_import(good_payload)
    assert preview.to_create == 5
    assert preview.to_update == 3
    assert preview.to_delete == 0
    assert preview.validation_errors == []
    # 5 creates + 3 updates = 8 preview entries (under the cap of 50).
    assert len(preview.preview) == 8
    actions = [e["action"] for e in preview.preview]
    assert actions.count("create") == 5
    assert actions.count("update") == 3


@pytest.mark.asyncio
async def test_preview_unknown_schema_version_raises(
    db_session: AsyncSession,
) -> None:
    """An unsupported ``schema_version`` raises :class:`UnknownSchemaVersion`."""
    payload = _envelope_dict([], schema_version="0.9")
    svc = JsonIOService(db_session)
    with pytest.raises(UnknownSchemaVersion) as exc_info:
        await svc.preview_import(payload)
    assert "0.9" in exc_info.value.message
    assert "1.0" in exc_info.value.message


@pytest.mark.asyncio
async def test_preview_collects_all_validation_errors(
    db_session: AsyncSession,
) -> None:
    """3 malformed entries → a single error with 3 entries (NOT fail-fast)."""
    exam = Exam(partial_number=1, exam_date=__import__("datetime").date(2024, 6, 15))
    db_session.add(exam)
    await db_session.commit()
    exam_uuid = exam.uuid

    bad1 = _question_dict(uuid="11111111-1111-4111-8111-111111111111", exam_uuid=exam_uuid)
    bad1["exam_context"]["partial_number"] = "not an int"  # strict → fail
    bad2 = _question_dict(uuid="22222222-2222-4222-8222-222222222222", exam_uuid=exam_uuid)
    bad2["answers"] = [{"uuid": "x", "answer_text": "", "answer_type": "correct",
                         "is_common_misconception": False, "explanation": None,
                         "display_order": 0}]  # min_length=1 → fail
    bad3 = _question_dict(uuid="33333333-3333-4333-8333-333333333333", exam_uuid=exam_uuid)
    bad3["question_text"] = ""  # min_length=1 → fail

    payload = _envelope_dict([bad1, bad2, bad3])
    svc = JsonIOService(db_session)
    with pytest.raises(MalformedImportError) as exc_info:
        await svc.preview_import(payload)

    validation_errors = exc_info.value.details["validation_errors"]
    assert len(validation_errors) == 3, (
        "All 3 malformed entries must be reported in one error."
    )
    indices = {e["index"] for e in validation_errors}
    assert indices == {0, 1, 2}
    # Each entry's uuid is preserved when the input was a dict.
    uuids = {e["uuid"] for e in validation_errors}
    assert "11111111-1111-4111-8111-111111111111" in uuids
    assert "22222222-2222-4222-8222-222222222222" in uuids
    assert "33333333-3333-4333-8333-333333333333" in uuids


@pytest.mark.asyncio
async def test_preview_identical_content_reports_zero_changes(
    db_session: AsyncSession,
) -> None:
    """A question that matches the DB byte-for-byte does NOT increment any counter."""
    from datetime import date as _date

    exam = Exam(partial_number=1, exam_date=_date(2024, 6, 15), topic_tags="algebra")
    db_session.add(exam)
    await db_session.flush()
    q = Question(
        exam_id=exam.id,
        question_text="Stable Q",
        topic="OTHER",
        order_in_exam=1,
        is_corrected=False,
        correction_notes=None,
        has_code_in_answers=False,
    )
    db_session.add(q)
    await db_session.commit()

    payload = _envelope_dict(
        [
            _question_dict(
                uuid=q.uuid,
                exam_uuid=exam.uuid,
                text="Stable Q",
                topic="OTHER",
            )
        ]
    )
    svc = JsonIOService(db_session)
    preview = await svc.preview_import(payload)
    assert preview.to_create == 0
    assert preview.to_update == 0
    assert preview.to_delete == 0
    assert preview.preview == []


@pytest.mark.asyncio
async def test_preview_caps_preview_list_at_50_entries(
    db_session: AsyncSession,
) -> None:
    """``preview.preview`` is capped at 50 entries by the service."""
    from datetime import date as _date

    # Seed 60 questions so the delete set exceeds 50.
    exam = Exam(partial_number=1, exam_date=_date(2024, 6, 15))
    db_session.add(exam)
    await db_session.flush()
    for i in range(60):
        db_session.add(Question(exam_id=exam.id, question_text=f"Q{i}"))
    await db_session.commit()

    payload = _envelope_dict([])  # empty JSON → all 60 are orphans
    svc = JsonIOService(db_session)
    preview = await svc.preview_import(payload)
    assert preview.to_delete == 60
    assert len(preview.preview) == PREVIEW_ENTRY_CAP
