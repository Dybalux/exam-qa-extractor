"""End-to-end tests for the import/export HTTP endpoints (PR 3a).

The service-layer contract is pinned by ``tests/test_json_io_service.py``
and ``tests/test_schemas_json_io.py``. This file proves the HTTP
boundary delivers the same contract over the wire:

* ``POST /api/v1/export`` returns 200 with a date-stamped JSON
  attachment body that parses back into :class:`ExportFileSchema`.
* The endpoint is registered at ``/api/v1/export`` (NOT nested under
  ``/api/v1/exams/``).
* The empty-DB and populated-DB round-trips work.

These tests use the ``client`` fixture from ``tests/conftest.py``,
which wires an :class:`httpx.AsyncClient` to the FastAPI app via
:class:`ASGITransport` and overrides ``get_db`` to use the in-memory
test database.

The ``POST /api/v1/import`` endpoint is intentionally a stub in this
PR (T3.2 / PR 3b owns the real flow); a focused "501 not implemented"
test lives here so a future regression that re-wires the route
incorrectly is caught at this layer.
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
from app.core.constants import AnswerType, TopicEnum  # noqa: F401
from app.models.answer import Answer  # noqa: F401
from app.models.exam import Exam  # noqa: F401
from app.models.question import Question  # noqa: F401
from app.schemas.json_io import ExportFileSchema

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
    assert m, (
        f"Content-Disposition missing filename: {content_disposition!r}"
    )
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
        topic=TopicEnum.OTHER.value,
        order_in_exam=1,
        difficulty=3,
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
    assert exported.difficulty == 3

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
        f"POST /api/v1/export expected 200, got {response.status_code}: "
        f"{response.text}"
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
async def test_import_endpoint_returns_501_not_implemented(
    client: AsyncClient,
) -> None:
    """``POST /api/v1/import`` is registered but returns 501 (PR 3b / T3.2).

    The route is intentionally a stub in this PR. The HTTP contract
    here is "the endpoint exists at ``/api/v1/import`` and signals
    'not implemented' to any caller". A future regression that:

    * removed the route → 404 instead of 501,
    * re-routed it to a different URL → 404 here, or
    * accidentally implemented it early → 200/201

    is caught by this test.
    """
    response = await client.post("/api/v1/import")
    assert response.status_code == 501, response.text
    body = response.json()
    # FastAPI's HTTPException serializes to ``{"detail": ...}``.
    assert "detail" in body, body
    assert "not yet implemented" in body["detail"], body


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
