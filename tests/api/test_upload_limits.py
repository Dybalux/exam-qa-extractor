"""Regression tests for bounded chunked upload reading (JD-06)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.import_export import import_envelope
from app.api.upload_limits import read_upload_bounded
from app.api.v1.endpoints.ui_content import ui_exam_upload
from app.dependencies import get_ocr_service, get_storage_service
from app.main import app
from app.models import Exam, Subject

pytestmark = pytest.mark.asyncio


class _TrackingStreamUpload:
    """Fake UploadFile that tracks chunk reads without materializing a huge payload."""

    def __init__(
        self,
        total_bytes: int,
        *,
        declared_size: int | None = None,
        filename: str = "oversized.bin",
    ) -> None:
        self._remaining = total_bytes
        self.size = declared_size
        self.filename = filename
        self.read_calls = 0
        self.bytes_read = 0

    async def read(self, size: int = -1) -> bytes:
        self.read_calls += 1
        if self._remaining <= 0:
            return b""
        if size < 0:
            to_emit = self._remaining
        else:
            to_emit = min(size, self._remaining)
        self._remaining -= to_emit
        self.bytes_read += to_emit
        return b"A" * to_emit


async def test_read_upload_bounded_rejects_declared_size_before_any_read() -> None:
    """When file.size > max_bytes, abort with 413 before calling file.read()."""
    upload = _TrackingStreamUpload(total_bytes=5 * 1024 * 1024, declared_size=500)

    with pytest.raises(HTTPException) as exc_info:
        await read_upload_bounded(upload, max_bytes=256, chunk_size=64)

    assert exc_info.value.status_code == 413
    assert upload.read_calls == 0
    assert upload.bytes_read == 0


async def test_read_upload_bounded_aborts_early_without_reading_full_stream() -> None:
    """When file.size is None, chunked reader stops at max_bytes + 1 and returns 413."""
    max_bytes = 200 * 1024  # 200 KiB
    total_stream = 10 * 1024 * 1024  # 10 MiB
    upload = _TrackingStreamUpload(total_bytes=total_stream, declared_size=None)

    with pytest.raises(HTTPException) as exc_info:
        await read_upload_bounded(upload, max_bytes=max_bytes, chunk_size=64 * 1024)

    assert exc_info.value.status_code == 413
    assert upload.bytes_read == max_bytes + 1
    assert upload.bytes_read < total_stream


async def test_read_upload_bounded_accepts_exact_limit() -> None:
    """A stream whose length equals max_bytes succeeds and returns all bytes."""
    max_bytes = 150 * 1024
    upload = _TrackingStreamUpload(total_bytes=max_bytes, declared_size=None)

    data = await read_upload_bounded(upload, max_bytes=max_bytes, chunk_size=64 * 1024)

    assert len(data) == max_bytes
    assert upload.bytes_read == max_bytes


async def test_import_envelope_aborts_oversized_stream_early(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """import_envelope aborts oversized streams early without reading the whole body."""
    monkeypatch.setattr(
        "app.api.import_export.get_settings",
        lambda: SimpleNamespace(max_import_size_mb=1),
    )
    max_bytes = 1 * 1024 * 1024
    upload = _TrackingStreamUpload(
        total_bytes=10 * 1024 * 1024,
        declared_size=None,
        filename="huge.json",
    )
    svc = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await import_envelope(
            response=None,  # type: ignore[arg-type]
            file=upload,  # type: ignore[arg-type]
            confirm=True,
            svc=svc,
        )

    assert exc_info.value.status_code == 413
    assert upload.bytes_read == max_bytes + 1
    svc.apply_import.assert_not_awaited()
    svc.preview_import.assert_not_awaited()


async def test_ui_exam_upload_aborts_oversized_stream_early(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ui_exam_upload aborts oversized streams early with 413 before saving to disk."""
    max_bytes = 128 * 1024  # 128 KiB
    monkeypatch.setattr(
        "app.api.v1.endpoints.ui_content.get_settings",
        lambda: SimpleNamespace(max_upload_size=max_bytes),
    )
    upload = _TrackingStreamUpload(
        total_bytes=5 * 1024 * 1024,
        declared_size=None,
        filename="huge.png",
    )
    exam_svc = AsyncMock()
    storage_svc = AsyncMock()
    ocr_svc = AsyncMock()
    q_svc = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await ui_exam_upload(
            exam_id=1,
            file=upload,  # type: ignore[arg-type]
            language="spa",
            exam_svc=exam_svc,
            storage_svc=storage_svc,
            ocr_svc=ocr_svc,
            q_svc=q_svc,
        )

    assert exc_info.value.status_code == 413
    assert upload.bytes_read == max_bytes + 1
    storage_svc.save_file.assert_not_awaited()
    ocr_svc.extract_from_path.assert_not_awaited()


async def test_ui_exam_upload_http_endpoint_returns_413_on_oversize(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP POST /api/v1/ui/exams/{id}/upload returns 413 when payload exceeds limit."""
    subject = Subject(name="Sistemas Operativos", slug="sistemas-operativos")
    db_session.add(subject)
    await db_session.flush()

    exam = Exam(partial_number=1, topic_tags="processes", subject_id=subject.id)
    db_session.add(exam)
    await db_session.commit()

    max_bytes = 1024
    monkeypatch.setattr(
        "app.api.v1.endpoints.ui_content.get_settings",
        lambda: SimpleNamespace(max_upload_size=max_bytes),
    )

    storage_mock = AsyncMock()
    ocr_mock = AsyncMock()
    app.dependency_overrides[get_storage_service] = lambda: storage_mock
    app.dependency_overrides[get_ocr_service] = lambda: ocr_mock
    try:
        response = await client.post(
            f"/api/v1/ui/exams/{exam.id}/upload",
            files={"file": ("oversize.png", b"X" * (max_bytes + 1), "image/png")},
        )
    finally:
        app.dependency_overrides.pop(get_storage_service, None)
        app.dependency_overrides.pop(get_ocr_service, None)

    assert response.status_code == 413, response.text
    storage_mock.save_file.assert_not_awaited()
    ocr_mock.extract_from_path.assert_not_awaited()
