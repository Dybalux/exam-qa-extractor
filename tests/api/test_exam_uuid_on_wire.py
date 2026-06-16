"""End-to-end tests proving the new `uuid` field reaches the HTTP wire.

The schema-level tests in `tests/schemas/test_uuid_exposure.py` prove that
the Pydantic response models include `uuid`. Those tests serialize in
isolation, without going through FastAPI's request/response machinery.
This file proves the field actually flows through the full HTTP stack:

    POST /api/v1/exams/      -> response body must contain uuid
    GET  /api/v1/exams/{id}  -> response body must contain the same uuid
    GET  /api/v1/exams/      -> every list item must contain a uuid

These tests use the `client` fixture from `tests/conftest.py`, which
wires an `httpx.AsyncClient` to the FastAPI app via `ASGITransport` and
overrides `get_db` to use the in-memory test database.
"""

from __future__ import annotations

import re

import pytest
from httpx import AsyncClient

# Importing the models is required so they register with `app.db.base.Base`
# before the `db_engine` fixture (in tests/conftest.py) calls
# `Base.metadata.create_all`. Without this, the in-memory test database
# has no tables and every endpoint that touches the DB raises
# "no such table: exams".
from app.models.answer import Answer  # noqa: F401
from app.models.exam import Exam  # noqa: F401
from app.models.question import Question  # noqa: F401

# Canonical uuid4 regex: 8-4-4-4-12 hex chars, with the version nibble
# being `4` and the variant nibble being one of `[89ab]`.
_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _assert_is_uuid4(value: object, context: str) -> str:
    """Assert the value is a v4 UUID string and return it."""
    assert isinstance(value, str), (
        f"{context}: uuid must be a string, got {type(value).__name__}"
    )
    assert _UUID4_RE.match(value), f"{context}: uuid is not a valid v4 UUID: {value!r}"
    return value


@pytest.mark.asyncio
async def test_create_exam_response_includes_uuid_on_wire(
    client: AsyncClient,
) -> None:
    """POST /api/v1/exams/ must return a 201 with `uuid` in the body."""
    response = await client.post(
        "/api/v1/exams/",
        json={
            "partial_number": 1,
            "exam_date": "2024-06-15",
            "topic_tags": "algebra",
        },
    )
    assert response.status_code == 201, response.text

    body = response.json()
    assert "uuid" in body, (
        f"Response body missing 'uuid' field. Got keys: {sorted(body)}"
    )
    _assert_is_uuid4(body["uuid"], "POST /api/v1/exams/ response")


@pytest.mark.asyncio
async def test_get_exam_response_includes_same_uuid_on_wire(
    client: AsyncClient,
) -> None:
    """GET /api/v1/exams/{id} must return the same uuid the POST returned."""
    create_resp = await client.post(
        "/api/v1/exams/",
        json={
            "partial_number": 2,
            "exam_date": "2024-07-20",
            "topic_tags": None,
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    exam_id = created["id"]
    created_uuid = _assert_is_uuid4(created["uuid"], "POST response uuid")

    get_resp = await client.get(f"/api/v1/exams/{exam_id}")
    assert get_resp.status_code == 200, get_resp.text
    fetched = get_resp.json()

    assert "uuid" in fetched, (
        f"GET response missing 'uuid' field. Got keys: {sorted(fetched)}"
    )
    assert fetched["uuid"] == created_uuid, (
        f"GET returned a different uuid than POST. "
        f"POST uuid={created_uuid!r}, GET uuid={fetched.get('uuid')!r}"
    )


@pytest.mark.asyncio
async def test_list_exams_includes_uuid_per_item_on_wire(
    client: AsyncClient,
) -> None:
    """GET /api/v1/exams/ must return a list where every item has a uuid."""
    # Create two distinct exams. partial_number is constrained to 1..4
    # by ExamService.create_exam, so we use distinct values within that
    # range and distinct dates to avoid the duplicate-guard raising.
    payloads = [
        {"partial_number": 1, "exam_date": "2024-01-15", "topic_tags": "a"},
        {"partial_number": 2, "exam_date": "2024-02-20", "topic_tags": "b"},
    ]
    for idx, payload in enumerate(payloads):
        resp = await client.post("/api/v1/exams/", json=payload)
        assert resp.status_code == 201, resp.text
        _assert_is_uuid4(resp.json()["uuid"], f"create #{idx} response")

    list_resp = await client.get("/api/v1/exams/")
    assert list_resp.status_code == 200, list_resp.text
    items = list_resp.json()
    assert isinstance(items, list)
    assert len(items) >= 2, f"Expected at least 2 exams in list, got {len(items)}"

    uuids = []
    for idx, item in enumerate(items):
        assert "uuid" in item, (
            f"List item #{idx} missing 'uuid' field. Got keys: {sorted(item)}"
        )
        uuids.append(_assert_is_uuid4(item["uuid"], f"list item #{idx}"))

    # No two exams should share a uuid (the whole point of the column).
    assert len(set(uuids)) == len(uuids), f"Duplicate uuids in list response: {uuids}"
