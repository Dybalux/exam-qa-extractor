# ruff: noqa: E402
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
from datetime import date

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
                answers=[
                    (f"A{q_idx}{a}", "correct" if a == 0 else "incorrect")
                    for a in range(4)
                ],
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
        "Expected at least one log record on logger 'app.services.json_io_service'"
    )


# ===========================================================================
# Tests for preview_import (T2.3)
# ===========================================================================

import pytest

from app.core.exceptions import MalformedImportError, UnknownSchemaVersion
from app.services.json_io_service import PREVIEW_ENTRY_CAP


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
    image_id: int | None = None,
    confidence_score: float | None = None,
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
        "image_id": image_id,
        "confidence_score": confidence_score,
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
    exam = Exam(
        partial_number=1,
        exam_date=__import__("datetime").date(2024, 6, 15),
        topic_tags="a",
    )
    db_session.add(exam)
    await db_session.flush()
    q = Question(exam_id=exam.id, question_text="Seed", is_corrected=False)
    db_session.add(q)
    await db_session.commit()

    from sqlalchemy import func
    from sqlalchemy import select as _select

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

    bad1 = _question_dict(
        uuid="11111111-1111-4111-8111-111111111111", exam_uuid=exam_uuid
    )
    bad1["exam_context"]["partial_number"] = "not an int"  # strict → fail
    bad2 = _question_dict(
        uuid="22222222-2222-4222-8222-222222222222", exam_uuid=exam_uuid
    )
    bad2["answers"] = [
        {
            "uuid": "x",
            "answer_text": "",
            "answer_type": "correct",
            "is_common_misconception": False,
            "explanation": None,
            "display_order": 0,
        }
    ]  # min_length=1 → fail
    bad3 = _question_dict(
        uuid="33333333-3333-4333-8333-333333333333", exam_uuid=exam_uuid
    )
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


# ===========================================================================
# Tests for apply_import (T2.4)
# ===========================================================================

import datetime as _dt

from sqlalchemy import func
from sqlalchemy import select as _select
from sqlalchemy.exc import IntegrityError

from app.schemas.json_io import ImportApplyResultSchema


async def _seed_exam(
    session: AsyncSession,
    partial_number: int = 1,
    exam_date: "_dt.date | None" = None,
    tags: str | None = "algebra",
) -> Exam:
    """Create and flush an Exam in the test session."""
    exam = Exam(
        partial_number=partial_number,
        exam_date=exam_date if exam_date is not None else _dt.date(2024, 6, 15),
        topic_tags=tags,
    )
    session.add(exam)
    await session.flush()
    return exam


async def _seed_question(
    session: AsyncSession,
    exam: Exam,
    text: str = "Q",
    topic: str = "OTHER",
    is_corrected: bool = False,
    answers: list[tuple[str, str]] | None = None,
) -> Question:
    """Create a Question with optional Answers."""
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
            session.add(
                Answer(
                    question_id=q.id,
                    answer_text=text,
                    answer_type=atype,
                    display_order=idx,
                )
            )
        await session.flush()
    return q


async def _row_counts(session: AsyncSession) -> dict[str, int]:
    """Return the count of exams/questions/answers in the DB."""
    return {
        "exams": (
            await session.execute(_select(func.count()).select_from(Exam))
        ).scalar_one(),
        "questions": (
            await session.execute(_select(func.count()).select_from(Question))
        ).scalar_one(),
        "answers": (
            await session.execute(_select(func.count()).select_from(Answer))
        ).scalar_one(),
    }


# ---------------------------------------------------------------------------
# (a) Mixed counts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_mixed_counts(db_session: AsyncSession) -> None:
    """Mixed envelope: 5 new / 3 updated / 1 deleted orphan, counts match.

    The DB starts with 1 exam, 4 questions (q1..q4) each with 1 answer.
    The JSON declares 5 new questions (q5..q9), updates q1..q3 with
    their answers modified (same uuid, different content), and
    removes q4 + its answer (orphans).

    Expected counts:
        created: 5 new questions + 5 new answers + 1 exam (re-upserted
                because the JSON declares it; if its fields match the
                DB row exactly, this is 0, otherwise 1). The seeded
                exam's tags differ from the JSON's "algebra", so the
                exam is also an update.
        updated: 3 questions (q1..q3) + 3 answers + 1 exam.
        deleted: 1 question (q4) + 1 answer (a4).
    """
    exam = await _seed_exam(db_session, partial_number=1, tags="original-tags")
    q1 = await _seed_question(
        db_session, exam, text="old Q1", answers=[("old A1", "correct")]
    )
    q2 = await _seed_question(
        db_session, exam, text="old Q2", answers=[("old A2", "correct")]
    )
    q3 = await _seed_question(
        db_session, exam, text="old Q3", answers=[("old A3", "correct")]
    )
    await _seed_question(
        db_session, exam, text="orphan Q4", answers=[("orphan A4", "correct")]
    )
    a1 = (
        await db_session.execute(_select(Answer).where(Answer.question_id == q1.id))
    ).scalar_one()
    a2 = (
        await db_session.execute(_select(Answer).where(Answer.question_id == q2.id))
    ).scalar_one()
    a3 = (
        await db_session.execute(_select(Answer).where(Answer.question_id == q3.id))
    ).scalar_one()
    await db_session.commit()

    exam_uuid = exam.uuid
    json_questions: list[dict] = []
    # 5 brand new questions
    for i in range(5):
        json_questions.append(
            _question_dict(
                uuid=f"0000000{i}-0000-4000-8000-00000000000{i}",
                exam_uuid=exam_uuid,
                text=f"new Q{i}",
            )
        )
    # 3 updated: q1, q2, q3 with different content (text + answer).
    json_questions.append(
        _question_dict(
            uuid=q1.uuid,
            exam_uuid=exam_uuid,
            text="updated Q1",
            is_corrected=True,
            answers=[_answer_dict(uuid=a1.uuid, text="updated A1", atype="incorrect")],
        )
    )
    json_questions.append(
        _question_dict(
            uuid=q2.uuid,
            exam_uuid=exam_uuid,
            text="updated Q2",
            is_corrected=True,
            answers=[_answer_dict(uuid=a2.uuid, text="updated A2", atype="incorrect")],
        )
    )
    json_questions.append(
        _question_dict(
            uuid=q3.uuid,
            exam_uuid=exam_uuid,
            text="updated Q3",
            is_corrected=True,
            answers=[_answer_dict(uuid=a3.uuid, text="updated A3", atype="incorrect")],
        )
    )
    # q4 is intentionally omitted (orphan)

    payload = _envelope_dict(json_questions)
    svc = JsonIOService(db_session)
    result = await svc.apply_import(payload)

    assert isinstance(result, ImportApplyResultSchema)
    # 5 created: 5 new questions (their answers are not in the JSON, so
    # 0 new answers from new questions; the exam already exists in the
    # DB, so the exam is "updated" not "created").
    assert result.created == 5
    # 7 updated: 3 questions + 3 answers + 1 exam (its tags changed).
    assert result.updated == 7
    # 2 deleted: 1 question (q4) + 1 answer (a4).
    assert result.deleted == 2
    assert result.applied_at.tzinfo is not None

    # DB state: 1 exam, 8 questions (4 original - 1 orphan + 5 new),
    # 3 answers (the updated ones; the new questions carry no answers).
    counts = await _row_counts(db_session)
    assert counts == {"exams": 1, "questions": 8, "answers": 3}


# ---------------------------------------------------------------------------
# (b) Rollback on IntegrityError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_rolls_back_on_integrity_error(
    db_session: AsyncSession,
) -> None:
    """Mid-import ``IntegrityError`` rolls back the whole transaction.

    The DB has 1 question. The JSON has 2 new questions. The second
    question's first answer has ``answer_type="BOGUS"`` -- the schema
    accepts it (``str`` is lax), but the DB has a CHECK constraint
    on ``answer_type IN ('correct', 'incorrect', 'partial')`` that
    rejects it. The first question and answer SHOULD be added to the
    session, but the ``IntegrityError`` on the second answer's INSERT
    must roll back the entire transaction.
    """
    # DB state: empty.
    payload = _envelope_dict(
        [
            _question_dict(
                uuid="00000001-0000-4000-8000-000000000001",
                exam_uuid="00000001-0000-4000-8000-000000000000",
                text="OK Q1",
                answers=[_answer_dict(uuid="a-1", text="A1", atype="correct")],
            ),
            _question_dict(
                uuid="00000002-0000-4000-8000-000000000002",
                exam_uuid="00000001-0000-4000-8000-000000000000",
                text="Bad Q2",
                answers=[
                    _answer_dict(
                        uuid="a-2",
                        text="A2",
                        atype="BOGUS",  # fails the DB CHECK constraint
                    )
                ],
            ),
        ]
    )
    svc = JsonIOService(db_session)
    with pytest.raises(IntegrityError):
        await svc.apply_import(payload)

    # The DB is still empty: the rollback reverted every INSERT.
    counts = await _row_counts(db_session)
    assert counts == {"exams": 0, "questions": 0, "answers": 0}


# ---------------------------------------------------------------------------
# (c) Rejects malformed (DB unchanged)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_rejects_malformed_db_unchanged(
    db_session: AsyncSession,
) -> None:
    """A malformed entry raises :class:`MalformedImportError` before any write."""
    exam = await _seed_exam(db_session, partial_number=1)
    await db_session.commit()
    before = await _row_counts(db_session)

    bad = _question_dict(
        uuid="00000001-0000-4000-8000-000000000001",
        exam_uuid=exam.uuid,
    )
    bad["exam_context"]["partial_number"] = 99  # out of ge=1, le=4
    payload = _envelope_dict([bad])
    svc = JsonIOService(db_session)
    with pytest.raises(MalformedImportError) as exc_info:
        await svc.apply_import(payload)
    assert len(exc_info.value.details["validation_errors"]) == 1

    # The DB is unchanged.
    after = await _row_counts(db_session)
    assert after == before


# ---------------------------------------------------------------------------
# (d) Overwrite by uuid
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_overwrites_existing_question_by_uuid(
    db_session: AsyncSession,
) -> None:
    """Updating the JSON for an existing uuid overwrites the DB row."""
    exam = await _seed_exam(db_session, partial_number=1)
    q = await _seed_question(
        db_session,
        exam,
        text="old text",
        is_corrected=False,
    )
    await db_session.commit()
    q_uuid = q.uuid

    payload = _envelope_dict(
        [
            _question_dict(
                uuid=q_uuid,
                exam_uuid=exam.uuid,
                text="new text",
                is_corrected=True,
            )
        ]
    )
    svc = JsonIOService(db_session)
    result = await svc.apply_import(payload)
    assert result.created == 0
    assert result.updated == 1
    assert result.deleted == 0

    # Verify the row was actually updated in the DB.
    refreshed = (
        await db_session.execute(_select(Question).where(Question.uuid == q_uuid))
    ).scalar_one()
    assert refreshed.question_text == "new text"
    assert refreshed.is_corrected is True


# ---------------------------------------------------------------------------
# (e) Orphan cascade
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_orphan_exam_removes_its_questions_and_answers(
    db_session: AsyncSession,
) -> None:
    """An exam not present in the JSON is deleted, with its children."""
    exam = await _seed_exam(db_session, partial_number=1)
    await _seed_question(db_session, exam, text="Q1", answers=[("A1", "correct")])
    await _seed_question(db_session, exam, text="Q2", answers=[("A2", "correct")])
    await db_session.commit()

    # Empty JSON: every DB row is an orphan.
    payload = _envelope_dict([])
    svc = JsonIOService(db_session)
    result = await svc.apply_import(payload)
    # 1 exam + 2 questions + 2 answers = 5 deletes.
    assert result.deleted == 5
    assert result.created == 0
    assert result.updated == 0

    counts = await _row_counts(db_session)
    assert counts == {"exams": 0, "questions": 0, "answers": 0}


# ---------------------------------------------------------------------------
# (f) Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_is_idempotent(db_session: AsyncSession) -> None:
    """Applying the same envelope twice → second is all-zero, DB unchanged."""
    payload = _envelope_dict(
        [
            _question_dict(
                uuid="00000001-0000-4000-8000-000000000001",
                exam_uuid="00000001-0000-4000-8000-000000000000",
                text="Q1",
                answers=[_answer_dict(uuid="a-1", text="A1", atype="correct")],
            )
        ]
    )
    svc = JsonIOService(db_session)

    # First apply: 1 new exam + 1 new question + 1 new answer.
    first = await svc.apply_import(payload)
    assert first.created == 3
    assert first.updated == 0
    assert first.deleted == 0

    # Second apply: all-zero.
    second = await svc.apply_import(payload)
    assert second.created == 0
    assert second.updated == 0
    assert second.deleted == 0


# ---------------------------------------------------------------------------
# (g) Collects all errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_collects_all_validation_errors(
    db_session: AsyncSession,
) -> None:
    """3 malformed entries → a single error with 3 entries (NOT fail-fast)."""
    bad1 = _question_dict(
        uuid="00000001-0000-4000-8000-000000000001",
        exam_uuid="00000001-0000-4000-8000-000000000000",
    )
    bad1["exam_context"]["partial_number"] = "not an int"
    bad2 = _question_dict(
        uuid="00000002-0000-4000-8000-000000000002",
        exam_uuid="00000001-0000-4000-8000-000000000000",
    )
    bad2["answers"] = [
        {
            "uuid": "x",
            "answer_text": "",
            "answer_type": "correct",
            "is_common_misconception": False,
            "explanation": None,
            "display_order": 0,
        }
    ]
    bad3 = _question_dict(
        uuid="00000003-0000-4000-8000-000000000003",
        exam_uuid="00000001-0000-4000-8000-000000000000",
    )
    bad3["question_text"] = ""

    payload = _envelope_dict([bad1, bad2, bad3])
    svc = JsonIOService(db_session)
    with pytest.raises(MalformedImportError) as exc_info:
        await svc.apply_import(payload)

    validation_errors = exc_info.value.details["validation_errors"]
    assert len(validation_errors) == 3
    indices = {e["index"] for e in validation_errors}
    assert indices == {0, 1, 2}


# ---------------------------------------------------------------------------
# (h) Atomicity / transaction boundary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_opens_exactly_one_transaction(
    db_session: AsyncSession,
) -> None:
    """``apply_import`` opens exactly one ``async with self.session.begin():``.

    We assert the contract by verifying the apply path commits
    successfully and the DB ends in the expected state -- if the
    code opened multiple transactions, the second would observe a
    state that the first had not yet committed.
    """
    payload = _envelope_dict(
        [
            _question_dict(
                uuid="00000001-0000-4000-8000-000000000001",
                exam_uuid="00000001-0000-4000-8000-000000000000",
                text="Q1",
            )
        ]
    )
    svc = JsonIOService(db_session)
    result = await svc.apply_import(payload)
    assert result.created == 2  # 1 exam + 1 question
    # The data is visible after the call returns, proving the
    # transaction committed.
    counts = await _row_counts(db_session)
    assert counts == {"exams": 1, "questions": 1, "answers": 0}


# ---------------------------------------------------------------------------
# (j) Per-field diff sensitivity (closes the verify-report WARNING on the
#     early-return branches of ``_question_matches_db``).
#
#     The helper compares every question/answer field one-by-one; if any
#     field differs, it returns ``False`` early. This parameterized case
#     walks the fields and pins the contract: a change in ANY of them
#     must register as ``to_update=1``.
# ---------------------------------------------------------------------------


from datetime import date as _date_mod

# Canonical baseline values used by every parameter case. Keeping them
# here (not in the fixture) makes it obvious that every case is a delta
# of exactly one field from this baseline.
_BASELINE_QUESTION = {
    "question_text": "Q",
    "extracted_text": "raw OCR",
    "topic": "OTHER",
    "order_in_exam": 1,
    "is_corrected": False,
    "correction_notes": None,
    "has_code_in_answers": False,
    "image_id": None,
    "confidence_score": None,
    "exam_partial_number": 1,
    "exam_date": _date_mod(2024, 6, 15),
    "exam_topic_tags": "algebra",
    "answer_text": "A",
    "answer_type": "correct",
    "answer_is_common_misconception": False,
    "answer_explanation": None,
    "answer_display_order": 0,
}


def _build_diff_payload(
    uuid: str,
    exam_uuid: str,
    delta_field: str,
    answer_uuid: str,
) -> dict:
    """Build a JSON envelope with the given field changed from the baseline.

    All other fields match the DB baseline (see ``_seed_baseline_question``
    below). The only delta is on the named field, so any ``to_update > 0``
    is attributable to that one comparison branch in
    ``_question_matches_db`` (or ``_answer_matches_db`` for answer fields).
    """
    q = {
        "question_text": _BASELINE_QUESTION["question_text"],
        "extracted_text": _BASELINE_QUESTION["extracted_text"],
        "topic": _BASELINE_QUESTION["topic"],
        "order_in_exam": _BASELINE_QUESTION["order_in_exam"],
        "is_corrected": _BASELINE_QUESTION["is_corrected"],
        "correction_notes": _BASELINE_QUESTION["correction_notes"],
        "has_code_in_answers": _BASELINE_QUESTION["has_code_in_answers"],
        "image_id": _BASELINE_QUESTION["image_id"],
        "confidence_score": _BASELINE_QUESTION["confidence_score"],
        "exam_context": {
            "uuid": exam_uuid,
            "partial_number": _BASELINE_QUESTION["exam_partial_number"],
            "exam_date": _BASELINE_QUESTION["exam_date"].isoformat(),
            "topic_tags": _BASELINE_QUESTION["exam_topic_tags"],
        },
        "answers": [
            {
                "uuid": answer_uuid,
                "answer_text": _BASELINE_QUESTION["answer_text"],
                "answer_type": _BASELINE_QUESTION["answer_type"],
                "is_common_misconception": _BASELINE_QUESTION[
                    "answer_is_common_misconception"
                ],
                "explanation": _BASELINE_QUESTION["answer_explanation"],
                "display_order": _BASELINE_QUESTION["answer_display_order"],
            }
        ],
    }

    # Apply the single-field delta. Each branch sets one entry; the rest
    # of the payload is the baseline.
    if delta_field == "question_text":
        q["question_text"] = "Q changed"
    elif delta_field == "extracted_text":
        q["extracted_text"] = "raw OCR changed"
    elif delta_field == "topic":
        q["topic"] = "MEMORY"
    elif delta_field == "order_in_exam":
        q["order_in_exam"] = 2
    elif delta_field == "is_corrected":
        q["is_corrected"] = True
    elif delta_field == "correction_notes":
        q["correction_notes"] = "needs review"
    elif delta_field == "has_code_in_answers":
        q["has_code_in_answers"] = True
    elif delta_field == "image_id":
        q["image_id"] = 999  # value mismatch; FK is not exercised here
    elif delta_field == "confidence_score":
        q["confidence_score"] = 0.5
    elif delta_field == "exam_partial_number":
        q["exam_context"]["partial_number"] = 2
    elif delta_field == "exam_date":
        q["exam_context"]["exam_date"] = "2024-09-20"
    elif delta_field == "exam_topic_tags":
        q["exam_context"]["topic_tags"] = "geometry"
    elif delta_field == "answer_text":
        q["answers"][0]["answer_text"] = "A changed"
    elif delta_field == "answer_type":
        q["answers"][0]["answer_type"] = "incorrect"
    elif delta_field == "answer_is_common_misconception":
        q["answers"][0]["is_common_misconception"] = True
    elif delta_field == "answer_explanation":
        q["answers"][0]["explanation"] = "because reasons"
    elif delta_field == "answer_display_order":
        q["answers"][0]["display_order"] = 7
    else:
        raise AssertionError(f"Unknown delta field: {delta_field}")

    return {
        "uuid": uuid,
        **q,
    }


async def _seed_baseline_question(
    session: AsyncSession,
) -> tuple[Exam, Question, Answer]:
    """Seed the DB with one question + one answer matching ``_BASELINE_QUESTION``."""
    exam = Exam(
        partial_number=_BASELINE_QUESTION["exam_partial_number"],
        exam_date=_BASELINE_QUESTION["exam_date"],
        topic_tags=_BASELINE_QUESTION["exam_topic_tags"],
    )
    session.add(exam)
    await session.flush()
    q = Question(
        exam_id=exam.id,
        question_text=_BASELINE_QUESTION["question_text"],
        extracted_text=_BASELINE_QUESTION["extracted_text"],
        topic=_BASELINE_QUESTION["topic"],
        order_in_exam=_BASELINE_QUESTION["order_in_exam"],
        is_corrected=_BASELINE_QUESTION["is_corrected"],
        correction_notes=_BASELINE_QUESTION["correction_notes"],
        has_code_in_answers=_BASELINE_QUESTION["has_code_in_answers"],
        image_id=_BASELINE_QUESTION["image_id"],
        confidence_score=_BASELINE_QUESTION["confidence_score"],
    )
    session.add(q)
    await session.flush()
    a = Answer(
        question_id=q.id,
        answer_text=_BASELINE_QUESTION["answer_text"],
        answer_type=_BASELINE_QUESTION["answer_type"],
        is_common_misconception=_BASELINE_QUESTION["answer_is_common_misconception"],
        explanation=_BASELINE_QUESTION["answer_explanation"],
        display_order=_BASELINE_QUESTION["answer_display_order"],
    )
    session.add(a)
    await session.commit()
    return exam, q, a


# The fields ``_question_matches_db`` compares.
_DIFF_SENSITIVITY_FIELDS = [
    "question_text",
    "extracted_text",
    "topic",
    "order_in_exam",
    "is_corrected",
    "correction_notes",
    "has_code_in_answers",
    "image_id",
    "confidence_score",
    "exam_partial_number",
    "exam_date",
    "exam_topic_tags",
    "answer_text",
    "answer_type",
    "answer_is_common_misconception",
    "answer_explanation",
    "answer_display_order",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("delta_field", _DIFF_SENSITIVITY_FIELDS)
async def test_preview_detects_change_in_each_field(
    db_session: AsyncSession, delta_field: str
) -> None:
    """A delta in ANY of the 17 fields the diff compares must register as ``to_update=1``.

    Pinned by the verify report as the missing branch coverage on
    ``_question_matches_db``'s early-return comparisons. Each parameter
    case is a JSON envelope that matches the DB on every field EXCEPT
    one; the diff MUST catch the change.
    """
    exam, q, a = await _seed_baseline_question(db_session)

    payload = _envelope_dict(
        [
            _build_diff_payload(
                uuid=q.uuid,
                exam_uuid=exam.uuid,
                delta_field=delta_field,
                answer_uuid=a.uuid,
            )
        ]
    )
    svc = JsonIOService(db_session)
    preview = await svc.preview_import(payload)
    assert preview.to_create == 0, (
        f"field {delta_field!r}: expected 0 creates, got {preview.to_create}"
    )
    assert preview.to_update == 1, (
        f"field {delta_field!r}: expected 1 update, got {preview.to_update} "
        "(the diff helper did not detect this change)"
    )
    assert preview.to_delete == 0


# ---------------------------------------------------------------------------
# (k) image_id FK failure → IntegrityError → rollback
#     (closes the verify-report SUGGESTION on a missing image_id round-trip test)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_rolls_back_on_missing_image_id_fk(
    db_session: AsyncSession,
) -> None:
    """An import that references a non-existent ``exam_images.id`` rolls back.

    The apply path round-trips ``image_id`` as-is (deliberately NOT
    severing to None). The safety net is the DB's FK constraint: if
    the destination DB lacks the referenced image row, the
    ``IntegrityError`` must roll back the entire transaction, leaving
    the DB in its pre-import state.
    """
    # DB is empty. Build a payload that references image_id=999 (no
    # ``exam_images`` row with that id exists).
    payload = _envelope_dict(
        [
            _question_dict(
                uuid="00000001-0000-4000-8000-000000000001",
                exam_uuid="00000001-0000-4000-8000-000000000000",
                text="Q1",
                image_id=999,  # FK target does not exist
            )
        ]
    )
    svc = JsonIOService(db_session)
    with pytest.raises(IntegrityError):
        await svc.apply_import(payload)

    # No rows should be persisted: the FK violation rolled back the
    # entire transaction (including the new exam and question).
    counts = await _row_counts(db_session)
    assert counts == {"exams": 0, "questions": 0, "answers": 0}
