"""Security regression tests for CSRF protection (JD-01) and Host validation (JD-04)."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.core.constants import AnswerType, PracticeMode
from app.dependencies import get_db, get_ocr_service, get_storage_service
from app.main import app
from app.models import Answer, Exam, PracticeSession, Question, Subject, Topic


@pytest_asyncio.fixture
async def raw_client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient wired to ``app`` WITHOUT default CSRF headers."""
    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://localhost:8000",
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)


async def _seed_exam_and_session(
    db_session: AsyncSession,
) -> tuple[Exam, PracticeSession]:
    """Create a subject, topic, exam, ready question, and active practice session."""
    subject = Subject(name="Sistemas Operativos", slug="sistemas-operativos")
    db_session.add(subject)
    await db_session.flush()

    topic = Topic(name="Procesos", slug="processes", subject_id=subject.id)
    db_session.add(topic)

    exam = Exam(partial_number=1, topic_tags="processes", subject_id=subject.id)
    db_session.add(exam)
    await db_session.flush()

    question = Question(
        exam_id=exam.id,
        question_text="What does fork() return to the child process?",
        topic_id=topic.id,
        is_corrected=True,
    )
    db_session.add(question)
    await db_session.flush()

    answer = Answer(
        question_id=question.id,
        answer_text="0",
        answer_type=AnswerType.CORRECT.value,
    )
    db_session.add(answer)

    practice_session = PracticeSession(
        user_session_id="test-session-csrf",
        mode=PracticeMode.RANDOM.value,
        exam_id=exam.id,
        total_questions=1,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(practice_session)
    await db_session.commit()
    return exam, practice_session


def _wipe_envelope_bytes() -> bytes:
    """Valid empty v1.0 envelope that would delete all questions if applied."""
    return json.dumps(
        {
            "schema_version": "1.0",
            "exported_at": "2026-01-01T00:00:00Z",
            "questions": [],
        }
    ).encode("utf-8")


# ── JD-01: CSRF protection on mutating /api/* endpoints ──────


@pytest.mark.parametrize(
    "attack_headers",
    [
        pytest.param({}, id="missing-x-requested-with"),
        pytest.param({"X-Requested-With": "   "}, id="blank-x-requested-with"),
        pytest.param(
            {
                "X-Requested-With": "XMLHttpRequest",
                "Sec-Fetch-Site": "cross-site",
            },
            id="sec-fetch-site-cross-site",
        ),
        pytest.param(
            {
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "http://evil.example",
            },
            id="foreign-origin",
        ),
        pytest.param(
            {
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "null",
            },
            id="null-origin",
        ),
        pytest.param(
            {
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "http://evil.example/drive-by.html",
            },
            id="foreign-referer-without-origin",
        ),
    ],
)
async def test_csrf_blocks_drive_by_import_without_touching_db(
    raw_client: AsyncClient,
    db_session: AsyncSession,
    attack_headers: dict[str, str],
) -> None:
    """Drive-by POST /api/v1/import?confirm=true returns 403 and leaves DB intact."""
    await _seed_exam_and_session(db_session)

    response = await raw_client.post(
        "/api/v1/import?confirm=true",
        files={"file": ("wipe.json", _wipe_envelope_bytes(), "application/json")},
        headers=attack_headers,
    )
    assert response.status_code == 403, response.text

    db_session.expire_all()
    remaining_questions = (await db_session.execute(select(Question))).scalars().all()
    assert len(remaining_questions) == 1


@pytest.mark.parametrize(
    "attack_headers",
    [
        pytest.param({}, id="missing-x-requested-with"),
        pytest.param(
            {
                "X-Requested-With": "XMLHttpRequest",
                "Sec-Fetch-Site": "cross-site",
            },
            id="sec-fetch-site-cross-site",
        ),
        pytest.param(
            {
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "https://attacker.example",
            },
            id="foreign-origin",
        ),
        pytest.param(
            {
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "null",
            },
            id="null-origin",
        ),
        pytest.param(
            {
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://attacker.example/form.html",
            },
            id="foreign-referer-without-origin",
        ),
    ],
)
async def test_csrf_blocks_drive_by_upload_without_touching_disk_or_db(
    raw_client: AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
    attack_headers: dict[str, str],
) -> None:
    """Drive-by POST /api/v1/ui/exams/{id}/upload returns 403 with zero disk/DB writes."""
    exam, _ = await _seed_exam_and_session(db_session)

    storage_mock = AsyncMock()
    ocr_mock = AsyncMock()
    app.dependency_overrides[get_storage_service] = lambda: storage_mock
    app.dependency_overrides[get_ocr_service] = lambda: ocr_mock
    try:
        response = await raw_client.post(
            f"/api/v1/ui/exams/{exam.id}/upload",
            files={"file": ("exam.png", b"not-written", "image/png")},
            data={"language": "spa"},
            headers=attack_headers,
        )
    finally:
        app.dependency_overrides.pop(get_storage_service, None)
        app.dependency_overrides.pop(get_ocr_service, None)

    assert response.status_code == 403, response.text
    storage_mock.save_file.assert_not_awaited()
    ocr_mock.extract_from_path.assert_not_awaited()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "attack_headers",
    [
        pytest.param({}, id="missing-x-requested-with"),
        pytest.param(
            {
                "X-Requested-With": "XMLHttpRequest",
                "Sec-Fetch-Site": "cross-site",
            },
            id="sec-fetch-site-cross-site",
        ),
        pytest.param(
            {
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "http://evil.example",
            },
            id="foreign-origin",
        ),
        pytest.param(
            {
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "null",
            },
            id="null-origin",
        ),
    ],
)
async def test_csrf_blocks_drive_by_empty_post_complete_session(
    raw_client: AsyncClient,
    db_session: AsyncSession,
    attack_headers: dict[str, str],
) -> None:
    """Drive-by empty POST /api/v1/ui/practice/sessions/{id}/complete returns 403."""
    _, practice_session = await _seed_exam_and_session(db_session)
    session_id = practice_session.id

    response = await raw_client.post(
        f"/api/v1/ui/practice/sessions/{session_id}/complete",
        headers=attack_headers,
    )
    assert response.status_code == 403, response.text

    db_session.expire_all()
    refreshed = await db_session.get(PracticeSession, session_id)
    assert refreshed is not None
    assert refreshed.is_completed is False


async def test_csrf_blocks_put_and_delete_without_header(
    raw_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PUT and DELETE mutations on /api/* also require CSRF checks."""
    exam, _ = await _seed_exam_and_session(db_session)
    exam_id = exam.id

    put_resp = await raw_client.put(
        f"/api/v1/ui/exams/{exam_id}",
        json={"partial_number": 2, "exam_date": None, "topic_tags": "mutated"},
    )
    assert put_resp.status_code == 403

    delete_resp = await raw_client.delete(f"/api/v1/ui/exams/{exam_id}?force=true")
    assert delete_resp.status_code == 403

    db_session.expire_all()
    still_exists = await db_session.get(Exam, exam_id)
    assert still_exists is not None
    assert still_exists.partial_number == 1


async def test_csrf_allows_same_origin_and_safe_methods(
    raw_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Legitimate same-origin mutations with X-Requested-With and safe GETs succeed."""
    _, practice_session = await _seed_exam_and_session(db_session)

    # Safe GET needs no X-Requested-With header.
    get_resp = await raw_client.get("/api/v1/ui/exams")
    assert get_resp.status_code == 200

    # Same-origin mutation with Fetch Metadata + Origin + X-Requested-With succeeds.
    post_resp = await raw_client.post(
        f"/api/v1/ui/practice/sessions/{practice_session.id}/complete",
        headers={
            "Origin": "http://localhost:8000",
            "Sec-Fetch-Site": "same-origin",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    assert post_resp.status_code == 200, post_resp.text
    assert post_resp.json()["is_completed"] is True


async def test_csrf_allows_same_origin_referer_when_origin_absent(
    raw_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Mutation with same-origin Referer (no Origin) and X-Requested-With succeeds."""
    _, practice_session = await _seed_exam_and_session(db_session)

    resp = await raw_client.post(
        f"/api/v1/ui/practice/sessions/{practice_session.id}/complete",
        headers={
            "Referer": "http://localhost:8000/practice/1",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    assert resp.status_code == 200, resp.text


async def test_cors_preflight_allows_x_requested_with(
    raw_client: AsyncClient,
) -> None:
    """CORS preflight from an allowed origin explicitly permits X-Requested-With."""
    resp = await raw_client.options(
        "/api/v1/import",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Requested-With",
        },
    )
    assert resp.status_code == 200, resp.text
    allow_headers = resp.headers.get("access-control-allow-headers", "").lower()
    assert "x-requested-with" in allow_headers


# ── JD-04: Host header validation (DNS rebinding protection) ─


def test_default_allowed_hosts_excludes_wildcards_and_test() -> None:
    """Default Settings.allowed_hosts only permits localhost loopback hosts."""
    s = Settings()
    assert s.allowed_hosts == ["localhost", "127.0.0.1", "[::1]"]
    assert "*" not in s.allowed_hosts
    assert "test" not in s.allowed_hosts


@pytest.mark.parametrize("host", ["localhost:8000", "127.0.0.1:8000", "localhost"])
async def test_trusted_host_allows_loopback_hosts(
    raw_client: AsyncClient,
    host: str,
) -> None:
    """Valid loopback Host headers pass TrustedHostMiddleware."""
    resp = await raw_client.get("/health", headers={"Host": host})
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("host", ["evil.example:8000", "evil.example", "test"])
async def test_trusted_host_rejects_untrusted_hosts_with_400(
    raw_client: AsyncClient,
    host: str,
) -> None:
    """Untrusted Host headers return HTTP 400 (blocks DNS rebinding)."""
    resp = await raw_client.get("/health", headers={"Host": host})
    assert resp.status_code == 400, resp.text

    mutating = await raw_client.post(
        "/api/v1/import?confirm=true",
        headers={"Host": host, "X-Requested-With": "XMLHttpRequest"},
    )
    assert mutating.status_code == 400, mutating.text


async def test_csrf_allows_vite_dev_proxied_same_origin_post(
    raw_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Vite dev proxy with changeOrigin=false preserves Host: localhost:5173 so same-origin POSTs succeed."""
    exam, _ = await _seed_exam_and_session(db_session)

    # Matching Host + Origin (Vite proxy with changeOrigin: false) succeeds.
    ok_resp = await raw_client.post(
        "/api/v1/ui/practice/sessions",
        json={
            "mode": PracticeMode.RANDOM.value,
            "exam_id": exam.id,
            "total_questions": 1,
        },
        headers={
            "Host": "localhost:5173",
            "Origin": "http://localhost:5173",
            "Sec-Fetch-Site": "same-origin",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    assert ok_resp.status_code == 201, ok_resp.text

    # Rewritten Host (what Vite's default changeOrigin: true sent) is rejected.
    rewritten_resp = await raw_client.post(
        "/api/v1/ui/practice/sessions",
        json={
            "mode": PracticeMode.RANDOM.value,
            "exam_id": exam.id,
            "total_questions": 1,
        },
        headers={
            "Host": "127.0.0.1:8000",
            "Origin": "http://localhost:5173",
            "Sec-Fetch-Site": "same-origin",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    assert rewritten_resp.status_code == 403, rewritten_resp.text
    assert "untrusted Origin" in rewritten_resp.json()["detail"]

    # Foreign Origin against proxied Host is still blocked.
    evil_resp = await raw_client.post(
        "/api/v1/ui/practice/sessions",
        json={
            "mode": PracticeMode.RANDOM.value,
            "exam_id": exam.id,
            "total_questions": 1,
        },
        headers={
            "Host": "localhost:5173",
            "Origin": "https://evil.example",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    assert evil_resp.status_code == 403, evil_resp.text


@pytest.mark.parametrize(
    "header_name,header_val",
    [
        ("Origin", "http://[invalid"),
        ("Origin", "http://evil]example"),
        ("Referer", "http://[invalid/path"),
    ],
)
async def test_csrf_malformed_ipv6_origin_returns_403_not_500(
    raw_client: AsyncClient,
    header_name: str,
    header_val: str,
) -> None:
    """Malformed IPv6 Origin/Referer headers return 403 instead of crashing with 500."""
    resp = await raw_client.post(
        "/api/v1/export",
        headers={
            header_name: header_val,
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.parametrize(
    "req_path,expected_location",
    [
        ("/app", "/"),
        ("/app/practice/3?tab=1", "/practice/3?tab=1"),
        ("/app//evil.example/phish", "/evil.example/phish"),
        ("/app///evil.example", "/evil.example"),
        ("/app/\\evil.example", "/evil.example"),
        ("/app/foo\\evil.example", "/"),
    ],
)
async def test_legacy_app_redirect_blocks_open_redirect(
    raw_client: AsyncClient,
    req_path: str,
    expected_location: str,
) -> None:
    """Legacy /app redirect strips leading slashes/backslashes and never redirects externally."""
    resp = await raw_client.get(req_path, follow_redirects=False)
    assert resp.status_code == 308, resp.text
    location = resp.headers["location"]
    assert location == expected_location
    assert not location.startswith("//")
