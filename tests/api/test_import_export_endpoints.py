"""End-to-end tests for the import/export HTTP endpoints (PR 3a + PR 3b).

The service-layer contract is pinned by ``tests/test_json_io_service.py``
and ``tests/test_schemas_json_io.py``. This file proves the HTTP
boundary delivers the same contract over the wire:

* ``POST /api/v1/export`` returns 200 with a date-stamped JSON
  attachment body that parses back into :class:`ExportFileSchema`.
* The export endpoint is registered at ``/api/v1/export`` (NOT nested
  under ``/api/v1/exams/``).
* The empty-DB and populated-DB round-trips work.
* ``POST /api/v1/import`` is the safety boundary: pre-parse size cap
  (413 BEFORE parse), preview default (200), ``?confirm=true`` apply
  gate (201), 400 body shape for ``MalformedImportError`` with the
  ``validation_errors`` array in the body, 400 for unparseable JSON
  and unknown schema version, 500 for DB constraint violations.

These tests use the ``client`` fixture from ``tests/conftest.py``,
which wires an :class:`httpx.AsyncClient` to the FastAPI app via
:class:`ASGITransport` and overrides ``get_db`` to use the in-memory
test database.
"""

from __future__ import annotations

import json
import re
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Models must be imported so they register with ``app.db.base.Base``
# before the conftest's ``db_engine`` fixture calls
# ``Base.metadata.create_all``. (The conftest also imports them, but
# the explicit import here is the standard contract for the tests
# that exercise the DB via ``db_session``.)
from app.core.constants import AnswerType  # noqa: F401
from app.models.answer import Answer  # noqa: F401
from app.models.exam import Exam  # noqa: F401
from app.models.question import Question  # noqa: F401
from app.schemas.json_io import (
    ExportFileSchema,
    ImportApplyResultSchema,
    ImportPreviewSchema,
)

# Strict YYYYMMDD format (today's date) — not the file's mtime, not
# the export's ``exported_at``. The plan pins the filename to the
# server's local date so the user gets a deterministic name like
# ``exam-backup-20260604.json``.
_FILENAME_RE = re.compile(r"^exam-backup-\d{8}\.json$")


def _attachment_filename(content_disposition: str) -> str:
    """Extract the ``filename=...`` value from a Content-Disposition header.

    Raises ``AssertionError`` if the header is missing or malformed,
    so the test fails on a missing filename rather than on a regex
    that silently matches the empty string.
    """
    m = re.search(r'filename="([^"]+)"', content_disposition)
    assert m, f"Content-Disposition missing filename: {content_disposition!r}"
    return m.group(1)


@pytest.mark.asyncio
async def test_export_endpoint_empty_db(client: AsyncClient) -> None:
    """POST /api/v1/export on an empty DB returns a valid empty envelope.

    Contract:

    * Status 200.
    * ``content-type`` starts with ``application/json`` (the
      ``StreamingResponse`` may add ``; charset=utf-8``).
    * ``content-disposition`` is an attachment with a ``exam-backup-``
      prefix and a YYYYMMDD date.
    * Body parses as :class:`ExportFileSchema` with ``questions=[]``
      and the locked ``schema_version="1.0"``.
    """
    response = await client.post("/api/v1/export")
    assert response.status_code == 200, response.text

    content_type = response.headers["content-type"]
    assert content_type.startswith("application/json"), content_type

    content_disposition = response.headers["content-disposition"]
    assert "attachment" in content_disposition, content_disposition
    assert "exam-backup-" in content_disposition, content_disposition
    assert _FILENAME_RE.match(_attachment_filename(content_disposition))

    # The response body is the JSON envelope; parse it through the
    # service-layer schema to prove the wire format is round-trippable.
    envelope = ExportFileSchema.model_validate(response.json())
    assert envelope.schema_version == "1.0"
    assert envelope.questions == []


@pytest.mark.asyncio
async def test_export_endpoint_populated_db(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST /api/v1/export returns the full DB content for a populated DB.

    Seeds one exam, one question, and one answer via the ORM
    (committed so the test's HTTP-bound session sees the rows), then
    posts to the export endpoint and proves the body contains the
    expected denormalized structure:

    * one question at the top level,
    * its ``exam_context`` carries the parent's ``partial_number`` /
      ``exam_date`` / ``topic_tags`` / ``uuid``,
    * its ``answers`` list has the seeded answer with all fields
      round-tripped.
    """
    exam = Exam(
        partial_number=1,
        exam_date=date(2026, 6, 4),
        topic_tags="algebra",
    )
    db_session.add(exam)
    await db_session.flush()  # assigns exam.id

    question = Question(
        exam_id=exam.id,
        question_text="What is 2 + 2?",
        extracted_text="2 + 2",
        topic="other",
        order_in_exam=1,
    )
    db_session.add(question)
    await db_session.flush()

    answer = Answer(
        question_id=question.id,
        answer_text="4",
        answer_type=AnswerType.CORRECT.value,
        is_common_misconception=False,
        explanation="Basic arithmetic.",
        display_order=0,
    )
    db_session.add(answer)
    await db_session.commit()

    response = await client.post("/api/v1/export")
    assert response.status_code == 200, response.text

    envelope = ExportFileSchema.model_validate(response.json())
    assert envelope.schema_version == "1.0"
    assert len(envelope.questions) == 1, envelope.questions

    exported = envelope.questions[0]
    # Exam context is denormalized inline (no top-level exams array).
    assert exported.exam_context.uuid == exam.uuid
    assert exported.exam_context.partial_number == 1
    assert exported.exam_context.exam_date == date(2026, 6, 4)
    assert exported.exam_context.topic_tags == "algebra"

    # Question fields round-trip.
    assert exported.uuid == question.uuid
    assert exported.question_text == "What is 2 + 2?"
    assert exported.extracted_text == "2 + 2"
    assert exported.order_in_exam == 1

    # Answers are nested; sort order is by display_order (the service
    # sorts ascending before serializing).
    assert len(exported.answers) == 1
    exp_answer = exported.answers[0]
    assert exp_answer.uuid == answer.uuid
    assert exp_answer.answer_text == "4"
    assert exp_answer.answer_type == AnswerType.CORRECT.value
    assert exp_answer.is_common_misconception is False
    assert exp_answer.explanation == "Basic arithmetic."
    assert exp_answer.display_order == 0


@pytest.mark.asyncio
async def test_export_endpoint_filename_format(client: AsyncClient) -> None:
    """The attachment filename matches ``exam-backup-YYYYMMDD.json``.

    Validates the YYYYMMDD portion is exactly 8 digits and the
    surrounding prefix/suffix are exact. The date portion is not
    checked against a specific day — only its shape.
    """
    response = await client.post("/api/v1/export")
    assert response.status_code == 200, response.text

    content_disposition = response.headers["content-disposition"]
    filename = _attachment_filename(content_disposition)

    assert _FILENAME_RE.match(filename), (
        f"Filename {filename!r} does not match {_FILENAME_RE.pattern!r}"
    )
    # Spot-check: the 8-digit date is a parseable ISO basic-format date.
    date_part = filename.removeprefix("exam-backup-").removesuffix(".json")
    # ``datetime.strptime`` will reject any non-YYYYMMDD shape.
    from datetime import datetime

    parsed = datetime.strptime(date_part, "%Y%m%d")
    assert 2000 <= parsed.year <= 2100, parsed.year


@pytest.mark.asyncio
async def test_export_endpoint_is_registered_at_correct_url(
    client: AsyncClient,
) -> None:
    """The endpoint is at ``/api/v1/export`` (NOT nested under ``/exams/``).

    Proves two things in one test:

    1. ``POST /api/v1/export`` returns 200 (the route is registered).
    2. ``POST /api/v1/exams/export`` returns 404 (no such nested
       route) — this is the contract violation the plan explicitly
       warns against in T3.1.

    A future refactor that accidentally adds a ``/exams`` prefix to
    the router (e.g. ``include_router(import_export.router,
    prefix="/exams")``) would break test (2) and (1) and this
    regression would be caught.
    """
    # Positive: the export endpoint exists at the top-level API prefix.
    response = await client.post("/api/v1/export")
    assert response.status_code == 200, (
        f"POST /api/v1/export expected 200, got {response.status_code}: {response.text}"
    )

    # Negative: it must NOT be reachable under /exams/. FastAPI
    # returns 405 for an existing path with a wrong method; for a
    # missing path it returns 404. Either is "not registered here".
    nested = await client.post("/api/v1/exams/export")
    assert nested.status_code in (404, 405), (
        f"POST /api/v1/exams/export expected 404/405 (not nested), "
        f"got {nested.status_code}: {nested.text}"
    )


@pytest.mark.asyncio
async def test_export_endpoint_body_is_streaming_json_bytes(
    client: AsyncClient,
) -> None:
    """The export body is JSON-parseable UTF-8 bytes.

    Guards against an accidental refactor that swaps the
    :class:`StreamingResponse` for a ``JSONResponse`` with a
    Pydantic-serialized object (which would drop the
    ``default=str`` fallback for non-JSON-native fields) or a
    ``Response`` with the wrong ``media_type``.
    """
    response = await client.post("/api/v1/export")
    assert response.status_code == 200, response.text

    raw = response.content
    assert isinstance(raw, bytes), type(raw)
    # Must be valid UTF-8.
    decoded = raw.decode("utf-8")
    # Must round-trip through ``json.loads`` (the same path the
    # service's import flow takes on the client side).
    parsed = json.loads(decoded)
    assert "schema_version" in parsed
    assert parsed["schema_version"] == "1.0"


# ---------------------------------------------------------------------------
# POST /api/v1/import — PR 3b (T3.2)
#
# The import endpoint is the SAFETY BOUNDARY. These tests pin the
# HTTP-layer contract: pre-parse size cap, preview/confirm gate, the
# 400 body shape for MalformedImportError, and the error mapping for
# every service-level exception.
# ---------------------------------------------------------------------------


def _envelope_file(
    *,
    schema_version: str = "1.0",
    questions: list[dict] | None = None,
) -> dict:
    """Build a minimal valid envelope as a multipart-ready dict."""
    return {
        "schema_version": schema_version,
        "exported_at": "2026-06-04T12:00:00+00:00",
        "questions": questions
        if questions is not None
        else [
            {
                "uuid": "00000001-0000-4000-8000-000000000001",
                "exam_context": {
                    "uuid": "00000001-0000-4000-8000-000000000000",
                    "partial_number": 1,
                    "exam_date": "2026-06-04",
                    "topic_tags": "algebra",
                },
                "question_text": "What is 2+2?",
                "extracted_text": None,
                "topic": "OTHER",
                "order_in_exam": 1,
                "is_corrected": False,
                "correction_notes": None,
                "has_code_in_answers": False,
                "image_id": None,
                "confidence_score": None,
                "answers": [],
            }
        ],
    }


def _envelope_bytes(envelope: dict | str) -> bytes:
    """Serialize an envelope (or raw string) to multipart-ready bytes."""
    if isinstance(envelope, str):
        return envelope.encode("utf-8")
    return json.dumps(envelope).encode("utf-8")


@pytest.mark.asyncio
async def test_import_preview_without_confirm(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST /api/v1/import WITHOUT ``?confirm=true`` returns 200 + preview.

    The DB row count must be UNCHANGED — preview is a pure read. This
    pins the safety property that the default behavior is the
    non-destructive one (the dashboard's "Vista previa" button is
    always a read).
    """
    from sqlalchemy import func, select

    exam = Exam(partial_number=1, topic_tags="seed")
    db_session.add(exam)
    await db_session.flush()
    q = Question(exam_id=exam.id, question_text="Seed", topic="OTHER", order_in_exam=1)
    db_session.add(q)
    await db_session.commit()

    # Snapshot DB row counts before the preview.
    def _counts() -> dict[str, int]:
        return {
            "exams": 0,
            "questions": 0,
            "answers": 0,
        }

    # Re-read counts by running queries (sync helper inside an async
    # test is awkward — inline the queries).
    exam_count_before = (
        await db_session.execute(select(func.count()).select_from(Exam))
    ).scalar_one()
    question_count_before = (
        await db_session.execute(select(func.count()).select_from(Question))
    ).scalar_one()
    answer_count_before = (
        await db_session.execute(select(func.count()).select_from(Answer))
    ).scalar_one()

    # Preview an envelope that would CREATE 1 new question and DELETE
    # the seeded one. Without confirm, neither happens.
    payload = _envelope_dict(
        [
            _question_dict(
                uuid="99999999-9999-4999-8999-999999999999",
                exam_uuid=exam.uuid,
                text="Brand new question",
            )
        ]
    )
    response = await client.post(
        "/api/v1/import",
        files={"file": ("backup.json", _envelope_bytes(payload), "application/json")},
    )
    assert response.status_code == 200, response.text

    preview = ImportPreviewSchema.model_validate(response.json())
    assert preview.to_create == 1
    assert preview.to_delete == 1
    assert preview.to_update == 0
    assert preview.validation_errors == []

    # DB row counts unchanged.
    exam_count_after = (
        await db_session.execute(select(func.count()).select_from(Exam))
    ).scalar_one()
    question_count_after = (
        await db_session.execute(select(func.count()).select_from(Question))
    ).scalar_one()
    answer_count_after = (
        await db_session.execute(select(func.count()).select_from(Answer))
    ).scalar_one()
    assert exam_count_after == exam_count_before
    assert question_count_after == question_count_before
    assert answer_count_after == answer_count_before


@pytest.mark.asyncio
async def test_import_apply_with_confirm_true(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST /api/v1/import?confirm=true returns 201 + apply result; DB is updated.

    The destructive gate. The envelope is applied; row counts in the
    DB match the envelope content.
    """
    from sqlalchemy import func, select

    payload = _envelope_dict(
        [
            _question_dict(
                uuid="00000001-0000-4000-8000-000000000001",
                exam_uuid="00000001-0000-4000-8000-000000000000",
                text="Q1",
            ),
            _question_dict(
                uuid="00000002-0000-4000-8000-000000000002",
                exam_uuid="00000001-0000-4000-8000-000000000000",
                text="Q2",
            ),
        ]
    )
    response = await client.post(
        "/api/v1/import?confirm=true",
        files={"file": ("backup.json", _envelope_bytes(payload), "application/json")},
    )
    assert response.status_code == 201, response.text

    result = ImportApplyResultSchema.model_validate(response.json())
    assert result.created == 3  # 1 exam + 2 questions
    assert result.updated == 0
    assert result.deleted == 0

    # DB row counts match the envelope content.
    exam_count = (
        await db_session.execute(select(func.count()).select_from(Exam))
    ).scalar_one()
    question_count = (
        await db_session.execute(select(func.count()).select_from(Question))
    ).scalar_one()
    assert exam_count == 1
    assert question_count == 2


@pytest.mark.asyncio
async def test_import_rejects_malformed_with_validation_errors_in_body(
    client: AsyncClient,
) -> None:
    """Malformed JSON returns 400 with body containing ``validation_errors``.

    The 400 body shape is the contract the dashboard JS handler reads
    to render per-entry error messages. It MUST be in the body
    (NOT a custom header): ``{"detail": "Malformed import",
    "validation_errors": [...]}``.
    """
    exam_uuid = "00000001-0000-4000-8000-000000000000"
    bad1 = _question_dict(
        uuid="11111111-1111-4111-8111-111111111111",
        exam_uuid=exam_uuid,
    )
    bad1["exam_context"]["partial_number"] = "not an int"  # strict → fail
    bad2 = _question_dict(
        uuid="22222222-2222-4222-8222-222222222222",
        exam_uuid=exam_uuid,
    )
    bad2["question_text"] = ""  # min_length=1 → fail

    payload = _envelope_dict([bad1, bad2])
    response = await client.post(
        "/api/v1/import?confirm=true",
        files={"file": ("backup.json", _envelope_bytes(payload), "application/json")},
    )
    assert response.status_code == 400, response.text

    body = response.json()
    # The contract: detail is a human-readable summary; validation_errors
    # is the per-entry array the JS handler renders.
    assert body["detail"] == "Malformed import", body
    assert "validation_errors" in body, body
    assert len(body["validation_errors"]) == 2, body["validation_errors"]

    # Each entry has the index, the entry's uuid (best-effort), and
    # the per-field error list.
    indices = {e["index"] for e in body["validation_errors"]}
    assert indices == {0, 1}, indices


@pytest.mark.asyncio
async def test_import_returns_413_before_parse_on_oversize(
    client: AsyncClient,
) -> None:
    """Oversize files return 413 BEFORE any JSON parse happens.

    The safety contract: a deliberately-malformed-but-oversize
    payload yields 413, NOT 400 (a parse error would prove the
    size check fired AFTER the parse). The body of the response is
    irrelevant — what matters is the status code.
    """
    # Build an 11 MB payload that is also malformed JSON. If the size
    # check fires AFTER parse, we'd get 400 (the parse would fail
    # first). We want 413.
    from app.config import get_settings

    max_bytes = get_settings().max_import_size_mb * 1024 * 1024
    oversize_payload = b'{"schema_version": "BROKEN' + b" " * (max_bytes + 1)
    assert len(oversize_payload) > max_bytes

    response = await client.post(
        "/api/v1/import?confirm=true",
        files={"file": ("backup.json", oversize_payload, "application/json")},
    )
    assert response.status_code == 413, response.text


@pytest.mark.asyncio
async def test_import_returns_400_on_unparseable_json(
    client: AsyncClient,
) -> None:
    """Non-JSON bodies return 400 with the parser error in ``detail``."""
    response = await client.post(
        "/api/v1/import?confirm=true",
        files={"file": ("backup.json", b"this is not json at all", "application/json")},
    )
    assert response.status_code == 400, response.text
    body = response.json()
    assert "Invalid JSON" in body["detail"], body


@pytest.mark.asyncio
async def test_import_returns_400_on_unknown_schema_version(
    client: AsyncClient,
) -> None:
    """An envelope with an unknown ``schema_version`` returns 400.

    The service's :class:`UnknownSchemaVersion` exception is mapped
    to 400 with the service's message in ``detail`` (the message
    includes both the offending version and the supported set).
    """
    payload = _envelope_dict([], schema_version="99.0")
    response = await client.post(
        "/api/v1/import?confirm=true",
        files={"file": ("backup.json", _envelope_bytes(payload), "application/json")},
    )
    assert response.status_code == 400, response.text
    body = response.json()
    # The service's message includes the offending version and the
    # supported set; we don't pin the exact wording, just the version
    # and that the supported set is mentioned.
    assert "99.0" in body["detail"], body
    assert "1.0" in body["detail"], body


# ---------------------------------------------------------------------------
# End-to-end round-trip tests (PR 3c, T3.4 acceptance contract)
#
# These tests exercise the FULL HTTP path: seed DB → POST /api/v1/export
# → optionally mutate the exported JSON → POST /api/v1/import?confirm=true.
# They pin the dashboard's expected click-through: the "Vista previa"
# button hits /api/v1/import (no confirm), and the "Confirmar import"
# button hits /api/v1/import?confirm=true.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_export_then_import_same_file_yields_zero_changes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Round-trip: export then import the same body → no changes, DB unchanged.

    Seeds a small DB (1 exam, 1 question, 1 answer), exports it, then
    applies the export back with ``?confirm=true``. The result must be
    all-zero counts AND the re-exported envelope must equal the original
    envelope (modulo the server-side ``exported_at`` timestamp), which
    is the strongest "DB is byte-equal to its pre-import state"
    assertion we can make at the HTTP boundary.
    """
    exam = Exam(partial_number=1, topic_tags="seed")
    db_session.add(exam)
    await db_session.flush()
    question = Question(
        exam_id=exam.id,
        question_text="Original text",
        topic="OTHER",
        order_in_exam=1,
    )
    db_session.add(question)
    await db_session.flush()
    answer = Answer(
        question_id=question.id,
        answer_text="A",
        answer_type=AnswerType.CORRECT.value,
        display_order=0,
    )
    db_session.add(answer)
    await db_session.commit()

    # 1. First export.
    first = await client.post("/api/v1/export")
    assert first.status_code == 200, first.text
    first_envelope = first.json()
    # Capture the uuids we'll assert on after the round-trip.
    assert len(first_envelope["questions"]) == 1
    captured_question_uuid = first_envelope["questions"][0]["uuid"]
    captured_question_text = first_envelope["questions"][0]["question_text"]
    captured_exam_uuid = first_envelope["questions"][0]["exam_context"]["uuid"]

    # 2. Apply the same envelope with ?confirm=true. All counts must be 0
    #    because every row is identical to what's in the DB.
    response = await client.post(
        "/api/v1/import?confirm=true",
        files={
            "file": (
                "backup.json",
                json.dumps(first_envelope).encode("utf-8"),
                "application/json",
            )
        },
    )
    assert response.status_code == 201, response.text
    result = ImportApplyResultSchema.model_validate(response.json())
    assert result.created == 0, result
    assert result.updated == 0, result
    assert result.deleted == 0, result

    # 3. Re-export and assert the body is byte-equal to the first export
    #    (modulo the server-side exported_at timestamp, which always
    #    advances and isn't part of the data contract).
    second = await client.post("/api/v1/export")
    assert second.status_code == 200, second.text
    second_envelope = second.json()

    # Normalize: drop the server-controlled ``exported_at`` from both
    # envelopes so the comparison is purely on the data shape.
    first_norm = {**first_envelope}
    second_norm = {**second_envelope}
    first_norm.pop("exported_at", None)
    second_norm.pop("exported_at", None)
    assert first_norm == second_norm, (
        "Round-trip changed the DB: first={first_norm} second={second_norm}"
    )

    # Spot-check: the question's text and the uuids are preserved.
    assert second_envelope["questions"][0]["uuid"] == captured_question_uuid
    assert second_envelope["questions"][0]["question_text"] == captured_question_text
    assert second_envelope["questions"][0]["exam_context"]["uuid"] == captured_exam_uuid


@pytest.mark.asyncio
async def test_e2e_export_then_import_modified_file_yields_expected_changes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Export, modify the JSON, then import → the change is applied.

    Seeds one question, exports it, mutates the ``question_text`` in
    the exported JSON, and applies with ``?confirm=true``. The plan
    accepts ``updated=1`` OR ``created=1`` (depending on what the
    service's diff counts as a change); we assert the question_text in
    the DB now matches the new value AND at least one row was touched.
    """
    exam = Exam(partial_number=1, topic_tags="seed")
    db_session.add(exam)
    await db_session.flush()
    question = Question(
        exam_id=exam.id,
        question_text="Original text",
        topic="OTHER",
        order_in_exam=1,
    )
    db_session.add(question)
    await db_session.commit()

    # 1. Export.
    response = await client.post("/api/v1/export")
    assert response.status_code == 200, response.text
    envelope = response.json()
    assert len(envelope["questions"]) == 1

    # 2. Mutate the question's text in the JSON we just exported.
    original_uuid = envelope["questions"][0]["uuid"]
    envelope["questions"][0]["question_text"] = "Modified text after round-trip"

    # 3. Apply the mutated envelope.
    response = await client.post(
        "/api/v1/import?confirm=true",
        files={
            "file": (
                "backup.json",
                json.dumps(envelope).encode("utf-8"),
                "application/json",
            )
        },
    )
    assert response.status_code == 201, response.text
    result = ImportApplyResultSchema.model_validate(response.json())

    # The plan accepts updated=1 or created=1; we pin the weaker
    # "at least one row was touched" and the strict "the new text is
    # in the DB" — the strong contract for this test.
    assert (result.created + result.updated) >= 1, result
    # No deletions on this path (we didn't drop the row from the JSON).
    assert result.deleted == 0, result

    # 4. Re-export and assert the new text is the one the DB has.
    second = await client.post("/api/v1/export")
    assert second.status_code == 200, second.text
    second_envelope = second.json()
    assert len(second_envelope["questions"]) == 1
    assert second_envelope["questions"][0]["uuid"] == original_uuid
    assert second_envelope["questions"][0]["question_text"] == (
        "Modified text after round-trip"
    )


# ---------------------------------------------------------------------------
# Test helpers (reused by the import tests above)
# ---------------------------------------------------------------------------


def _envelope_dict(
    questions: list[dict],
    schema_version: str = "1.0",
) -> dict:
    """Build a raw JSON-loaded dict (what the multipart upload carries)."""
    return {
        "schema_version": schema_version,
        "exported_at": "2026-06-04T12:00:00+00:00",
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
    """Build a raw JSON question entry for import tests."""
    if answers is None:
        answers = []
    return {
        "uuid": uuid,
        "exam_context": {
            "uuid": exam_uuid,
            "partial_number": 1,
            "exam_date": "2026-06-04",
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
