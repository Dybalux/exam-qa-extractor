"""Tests for post-save redirect targets, flash encoding, and return_to validation.

Covers SDD change ``fix-exam-list-and-edit-navigation`` tasks 5.1–5.3.
"""

import urllib.parse

import pytest
from fastapi.responses import RedirectResponse
from httpx import AsyncClient

# ── 5.1 redirect_with_flash URL-encoding ─────────────────────
from app.api._flash import redirect_with_flash


@pytest.mark.parametrize(
    "message,expected_substring",
    [
        ("foo & bar", "foo%20%26%20bar"),
        ("hash # test", "hash%20%23%20test"),
        ("hello world", "hello%20world"),
        ("con ó", "con%20%C3%B3"),
    ],
)
def test_redirect_with_flash_encodes_special_chars(
    message: str, expected_substring: str
):
    """Message with special chars must be URL-encoded in the redirect URL."""
    resp = redirect_with_flash("/exams", message, "success")
    assert isinstance(resp, RedirectResponse)
    assert resp.status_code == 303

    location = resp.headers["location"]
    assert expected_substring in location
    # type param must also be present and unchanged.
    assert "type=success" in location


def test_redirect_with_flash_appends_to_url_with_existing_query():
    """When the target URL already has query params, use & as separator."""
    resp = redirect_with_flash("/exams?foo=bar", "ok", "info")
    location = resp.headers["location"]
    assert location.startswith("/exams?foo=bar&")
    assert "message=ok" in location
    assert "type=info" in location


# ── 5.2 return_to open-redirect validation ───────────────────


@pytest.mark.asyncio
async def test_upload_exam_image_with_invalid_return_to_uses_default(
    client: AsyncClient,
):
    """When return_to is an absolute or unknown URL, the default is used.

    This test exercises the ``_validate_return_to`` helper directly
    (rejecting absolute/unknown paths and accepting allowlist entries).
    The endpoint behaviour — success redirect with a valid ``return_to``
    form field and the default fallback when absent — is covered by the
    dedicated ``test_upload_exam_image_*`` endpoint tests below.
    """
    from app.api.exams import _validate_return_to

    # Absolute URLs must be rejected.
    assert _validate_return_to("//evil.com", 1) is None
    assert _validate_return_to("https://evil.com", 1) is None

    # Unknown paths must be rejected.
    assert _validate_return_to("/unknown", 1) is None
    assert _validate_return_to("/exams/5/extra", 1) is None

    # Valid allowlist paths must be accepted.
    valid_needs_review = _validate_return_to("/search/needs-review", 1)
    assert valid_needs_review is not None
    assert "/search/needs-review" in valid_needs_review
    assert "exam_id=1" in valid_needs_review

    # /exams/{id} path must be pinned to the route exam_id (1, not 999).
    valid_exam = _validate_return_to("/exams/999", 1)
    assert valid_exam is not None
    assert "/exams/1" in valid_exam
    assert "exam_id=1" in valid_exam


def test_validate_return_to_preserves_existing_query_params():
    """Query params from the original return_to are preserved + exam_id injected."""
    from app.api.exams import _validate_return_to

    result = _validate_return_to("/search/needs-review?foo=bar", 5)
    assert result is not None
    parsed = urllib.parse.urlsplit(result)
    qs = urllib.parse.parse_qs(parsed.query)
    assert qs["foo"] == ["bar"]
    assert qs["exam_id"] == ["5"]


# ── 5.3 Redirect target URLs ─────────────────────────────────


@pytest.mark.asyncio
async def test_exam_create_redirects_to_list(client: AsyncClient):
    """POST /exams/new → 303 redirect to /exams with flash message."""
    response = await client.post(
        "/exams/new",
        data={
            "partial_number": "3",
            "exam_date": "2025-06-15",
            "topic_tags": "procesos",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/exams?")
    assert "message=" in location
    # "Examen guardado" encoded.
    assert "Examen" in urllib.parse.unquote(location)


@pytest.mark.asyncio
async def test_exam_edit_submit_redirects_to_list_with_flash(
    client: AsyncClient,
):
    """POST /exams/{id}/edit → 303 redirect to /exams with flash.

    Before this change, the handler returned a bare RedirectResponse
    with NO flash.  After the change, it must include a flash message.
    """
    # Create an exam via the API to get a real ID.
    api_create = await client.post(
        "/api/v1/exams/",
        json={"partial_number": 2, "topic_tags": "memoria"},
    )
    created = api_create.json()
    exam_id = created["id"]

    # Now edit.
    edit_resp = await client.post(
        f"/exams/{exam_id}/edit",
        data={"partial_number": "2", "topic_tags": "memoria"},
        follow_redirects=False,
    )
    assert edit_resp.status_code == 303
    location = edit_resp.headers["location"]
    assert location.startswith("/exams?")
    decoded = urllib.parse.unquote(location)
    assert "Examen guardado" in decoded


@pytest.mark.asyncio
async def test_manual_question_create_redirects_to_question_list(
    client: AsyncClient,
    default_subject,
):
    """POST /exams/{id}/questions/new → 303 redirect to /questions."""
    # default_subject seeds the 'other' topic needed by the handler.
    _ = default_subject
    # Create an exam via API.
    api_create = await client.post(
        "/api/v1/exams/",
        json={"partial_number": 3, "topic_tags": "test"},
    )
    exam_id = api_create.json()["id"]

    response = await client.post(
        f"/exams/{exam_id}/questions/new",
        data={
            "question_text": "¿Qué es un proceso?",
            "topic": "other",
            "correct_answer_text": "Es una entidad en ejecución.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/questions?")
    decoded = urllib.parse.unquote(location)
    assert "Pregunta guardada" in decoded


@pytest.mark.asyncio
async def test_ocr_correction_redirects_to_question_list(
    client: AsyncClient,
    default_subject,
):
    """POST /questions/{id}/correct → 303 redirect to /questions."""
    _ = default_subject
    # Create an exam + a question.
    api_create = await client.post(
        "/api/v1/exams/",
        json={"partial_number": 4, "topic_tags": "test"},
    )
    exam_id = api_create.json()["id"]

    q_create = await client.post(
        f"/exams/{exam_id}/questions/new",
        data={
            "question_text": "Pregunta de prueba OCR",
            "topic": "other",
            "correct_answer_text": "Respuesta",
        },
        follow_redirects=False,
    )
    assert q_create.status_code == 303

    # Find the created question ID via the API.
    api_q_resp = await client.get("/api/v1/questions/?exam_id=" + str(exam_id))
    questions = api_q_resp.json()
    assert len(questions) > 0
    question_id = questions[0]["id"]

    # Post correction.
    response = await client.post(
        f"/questions/{question_id}/correct",
        data={"corrected_text": "Texto corregido"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/questions?")
    decoded = urllib.parse.unquote(location)
    assert "Corrección guardada" in decoded


@pytest.mark.asyncio
async def test_answer_create_redirects_to_parent_question(
    client: AsyncClient,
    default_subject,
):
    """POST answer create/edit → 303 redirect to /questions/{qid} (parent detail).

    Covers the spec scenario "Answer create/edit redirects to parent
    question detail" — pages.py answer_create (line ~503) and
    answer_update (line ~556).
    """
    _ = default_subject  # seeds the 'other' topic needed by the handler
    # Create an exam + question.
    api_create = await client.post(
        "/api/v1/exams/",
        json={"partial_number": 1, "topic_tags": "test"},
    )
    exam_id = api_create.json()["id"]

    q_create = await client.post(
        f"/exams/{exam_id}/questions/new",
        data={
            "question_text": "¿Qué es la memoria virtual?",
            "topic": "other",
            "correct_answer_text": "Técnica de gestión de memoria.",
        },
        follow_redirects=False,
    )
    assert q_create.status_code == 303

    api_q_resp = await client.get("/api/v1/questions/?exam_id=" + str(exam_id))
    question_id = api_q_resp.json()[0]["id"]

    # Create answer via form → redirect to /questions/{qid}.
    create_resp = await client.post(
        f"/questions/{question_id}/answers/new",
        data={
            "answer_text": "Área de almacenamiento temporal.",
            "answer_type": "incorrect",
        },
        follow_redirects=False,
    )
    assert create_resp.status_code == 303
    location = create_resp.headers["location"]
    assert location.startswith(f"/questions/{question_id}?")
    decoded = urllib.parse.unquote(location)
    assert "Respuesta agregada correctamente" in decoded

    # Find the created answer ID via the API.
    api_a_resp = await client.get(f"/api/v1/answers/question/{question_id}")
    answer_id = api_a_resp.json()[0]["id"]

    # Edit answer via form → redirect to /questions/{qid}.
    edit_resp = await client.post(
        f"/questions/{question_id}/answers/{answer_id}/edit",
        data={
            "answer_text": "Área de almacenamiento temporal corregida.",
            "answer_type": "correct",
        },
        follow_redirects=False,
    )
    assert edit_resp.status_code == 303
    location = edit_resp.headers["location"]
    assert location.startswith(f"/questions/{question_id}?")
    decoded = urllib.parse.unquote(location)
    assert "Respuesta actualizada correctamente" in decoded


# ── 5.2b Upload endpoint return_to (success-path override) ────


@pytest.mark.asyncio
async def test_upload_exam_image_with_valid_return_to_redirects_to_return_to(
    client: AsyncClient,
    default_subject,
):
    """POST /api/v1/exams/{id}/upload with valid return_to → 303 to return_to.

    The success-path override fires: the redirect targets the validated
    return_to path (pinned exam_id), not the default review queue.
    OCR and storage are mocked at the dependency boundary.
    """
    from unittest.mock import AsyncMock, MagicMock

    from app.dependencies import get_ocr_service, get_storage_service
    from app.main import app
    from app.services.ocr_service import ExtractedQuestion, OCRResult

    _ = default_subject  # seeds 'other' topic used by the endpoint
    api_create = await client.post(
        "/api/v1/exams/",
        json={"partial_number": 2, "topic_tags": "test"},
    )
    exam_id = api_create.json()["id"]

    # Mock storage + OCR at the dependency boundary.
    storage_mock = MagicMock()
    upload_result_mock = MagicMock()
    upload_result_mock.absolute_path = "/tmp/test-upload.png"
    storage_mock.save_file = AsyncMock(return_value=upload_result_mock)

    ocr_mock = MagicMock()
    ocr_mock.process_image = AsyncMock(
        return_value=OCRResult(
            full_text="¿Pregunta?",
            questions=[
                ExtractedQuestion(
                    order=1, text="¿Pregunta?", confidence=50.0, requires_review=True
                )
            ],
            has_code=False,
            average_confidence=50.0,
        )
    )

    app.dependency_overrides[get_storage_service] = lambda: storage_mock
    app.dependency_overrides[get_ocr_service] = lambda: ocr_mock
    try:
        response = await client.post(
            f"/api/v1/exams/{exam_id}/upload",
            files={"file": ("test.png", b"fake-image-data", "image/png")},
            data={"language": "spa", "return_to": f"/exams/{exam_id}"},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(get_storage_service, None)
        app.dependency_overrides.pop(get_ocr_service, None)

    assert response.status_code == 303
    location = response.headers["location"]
    # return_to /exams/{id} is validated + pinned: /exams/{exam_id}?exam_id={exam_id}
    assert location.startswith(f"/exams/{exam_id}?")
    assert "exam_id=" in location


@pytest.mark.asyncio
async def test_upload_exam_image_without_return_to_uses_default_redirect(
    client: AsyncClient,
    default_subject,
):
    """POST /api/v1/exams/{id}/upload without return_to → 303 to default.

    With no return_to, the default redirect fires (review queue when
    questions need review). OCR and storage are mocked at the dependency
    boundary.
    """
    from unittest.mock import AsyncMock, MagicMock

    from app.dependencies import get_ocr_service, get_storage_service
    from app.main import app
    from app.services.ocr_service import ExtractedQuestion, OCRResult

    _ = default_subject
    api_create = await client.post(
        "/api/v1/exams/",
        json={"partial_number": 3, "topic_tags": "test"},
    )
    exam_id = api_create.json()["id"]

    storage_mock = MagicMock()
    upload_result_mock = MagicMock()
    upload_result_mock.absolute_path = "/tmp/test-upload.png"
    storage_mock.save_file = AsyncMock(return_value=upload_result_mock)

    ocr_mock = MagicMock()
    ocr_mock.process_image = AsyncMock(
        return_value=OCRResult(
            full_text="¿Pregunta?",
            questions=[
                ExtractedQuestion(
                    order=1, text="¿Pregunta?", confidence=50.0, requires_review=True
                )
            ],
            has_code=False,
            average_confidence=50.0,
        )
    )

    app.dependency_overrides[get_storage_service] = lambda: storage_mock
    app.dependency_overrides[get_ocr_service] = lambda: ocr_mock
    try:
        response = await client.post(
            f"/api/v1/exams/{exam_id}/upload",
            files={"file": ("test.png", b"fake-image-data", "image/png")},
            data={"language": "spa"},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(get_storage_service, None)
        app.dependency_overrides.pop(get_ocr_service, None)

    assert response.status_code == 303
    location = response.headers["location"]
    # Default: review queue (questions need review).
    assert location.startswith("/search/needs-review?")
    assert f"exam_id={exam_id}" in location
