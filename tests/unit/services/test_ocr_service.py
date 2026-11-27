"""Focused unit tests for OCRService hardening (JD-07)."""

from __future__ import annotations

import asyncio
import io
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import fitz
import pytest
from PIL import Image

from app.core.exceptions import OCRProcessingError
from app.services.ocr_service import (
    MAX_OCR_IMAGE_PIXELS,
    OCRService,
)


def _make_service(
    monkeypatch: pytest.MonkeyPatch,
    *,
    timeout: float | None = None,
    max_pixels: int | None = None,
) -> OCRService:
    """Construct an OCRService without requiring a host tesseract binary."""
    monkeypatch.setattr(
        "app.services.ocr_service.pytesseract.get_tesseract_version", lambda: "5.3.0"
    )
    return OCRService(timeout=timeout, max_pixels=max_pixels)


def _fake_pdf_doc(pages: list[MagicMock]) -> MagicMock:
    """Build a context-manager mock mimicking fitz.Document."""
    doc = MagicMock()
    doc.__enter__.return_value = doc
    doc.__exit__.return_value = False
    doc.__len__.return_value = len(pages)
    doc.__getitem__.side_effect = lambda idx: pages[idx]
    return doc


# ── Defect 1: fitz.open context manager & 0-page / error cleanup ──


def test_pdf_to_image_rejects_zero_page_pdf_and_closes_handle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """0-page PDFs raise OCRProcessingError without indexing doc[0] and close fitz doc."""
    svc = _make_service(monkeypatch)
    doc = _fake_pdf_doc([])
    monkeypatch.setattr("app.services.ocr_service.fitz.open", lambda _p: doc)

    with pytest.raises(OCRProcessingError, match="no pages"):
        svc._pdf_to_image(tmp_path / "empty.pdf")

    doc.__getitem__.assert_not_called()
    doc.__exit__.assert_called_once()


def test_extract_text_from_pdf_direct_handles_zero_page_and_closes_handle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """0-page PDFs in direct extraction return None and close fitz doc."""
    svc = _make_service(monkeypatch)
    doc = _fake_pdf_doc([])
    monkeypatch.setattr("app.services.ocr_service.fitz.open", lambda _p: doc)

    assert svc._extract_text_from_pdf_direct(tmp_path / "empty.pdf") is None
    doc.__exit__.assert_called_once()


def test_extract_text_from_pdf_direct_closes_handle_on_page_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Exceptions during direct PDF text extraction still close the fitz document."""
    svc = _make_service(monkeypatch)
    bad_page = MagicMock()
    bad_page.get_text.side_effect = RuntimeError("corrupt PDF stream")
    doc = _fake_pdf_doc([bad_page])
    monkeypatch.setattr("app.services.ocr_service.fitz.open", lambda _p: doc)

    assert svc._extract_text_from_pdf_direct(tmp_path / "broken.pdf") is None
    doc.__exit__.assert_called_once()


def test_pdf_to_image_closes_handle_on_render_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Exceptions during get_pixmap still close the fitz document."""
    svc = _make_service(monkeypatch)
    bad_page = MagicMock()
    bad_page.rect = SimpleNamespace(width=500.0, height=700.0)
    bad_page.get_pixmap.side_effect = RuntimeError("render boom")
    doc = _fake_pdf_doc([bad_page])
    monkeypatch.setattr("app.services.ocr_service.fitz.open", lambda _p: doc)

    with pytest.raises(OCRProcessingError, match="Failed to process PDF"):
        svc._pdf_to_image(tmp_path / "broken.pdf")

    doc.__exit__.assert_called_once()


# ── Defect 2: Pixel budget enforcement before rendering / decoding ──


def test_pdf_to_image_rejects_pixel_bomb_before_get_pixmap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Oversized PDF pages are rejected BEFORE get_pixmap allocates a giant bitmap."""
    svc = _make_service(monkeypatch)
    bomb_page = MagicMock()
    # At 2x scale: 6000 * 6000 = 36,000,000 > MAX_OCR_IMAGE_PIXELS (25,000,000).
    bomb_page.rect = SimpleNamespace(width=3000.0, height=3000.0)
    doc = _fake_pdf_doc([bomb_page])
    monkeypatch.setattr("app.services.ocr_service.fitz.open", lambda _p: doc)

    with pytest.raises(OCRProcessingError, match="exceed maximum OCR budget"):
        svc._pdf_to_image(tmp_path / "bomb.pdf")

    bomb_page.get_pixmap.assert_not_called()
    doc.__exit__.assert_called_once()


def test_pdf_to_image_rejects_real_oversized_pdf_before_get_pixmap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A real PyMuPDF oversized page is rejected before Page.get_pixmap runs."""
    svc = _make_service(monkeypatch)
    pdf_path = tmp_path / "giant_page.pdf"
    with fitz.open() as created:
        # 4000pt x 4000pt -> 8000px x 8000px = 64,000,000 pixels at 2x scale.
        created.new_page(width=4000, height=4000)
        created.save(pdf_path)

    get_pixmap_called = False

    def _forbid_get_pixmap(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        nonlocal get_pixmap_called
        get_pixmap_called = True
        raise AssertionError("get_pixmap must not be called on pixel-bomb PDFs")

    monkeypatch.setattr(fitz.Page, "get_pixmap", _forbid_get_pixmap)

    with pytest.raises(OCRProcessingError, match="exceed maximum OCR budget"):
        svc._pdf_to_image(pdf_path)

    assert get_pixmap_called is False


def test_pdf_to_image_renders_valid_pdf_as_rgb_without_alpha(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Valid PDF pages invoke get_pixmap(..., alpha=False, colorspace=fitz.csRGB)."""
    svc = _make_service(monkeypatch)
    page = MagicMock()
    page.rect = SimpleNamespace(width=100.0, height=100.0)
    # 200x200 RGB pixmap
    page.get_pixmap.return_value = SimpleNamespace(
        width=200,
        height=200,
        samples=b"\xff" * (200 * 200 * 3),
    )
    doc = _fake_pdf_doc([page])
    monkeypatch.setattr("app.services.ocr_service.fitz.open", lambda _p: doc)

    img = svc._pdf_to_image(tmp_path / "ok.pdf")

    assert img.mode == "RGB"
    assert img.size == (200, 200)
    _, kwargs = page.get_pixmap.call_args
    assert kwargs["alpha"] is False
    assert kwargs["colorspace"] is fitz.csRGB
    doc.__exit__.assert_called_once()


def test_pillow_image_pixel_bomb_rejected_before_decoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Oversized PIL images are rejected on header size BEFORE img.load() decodes pixels."""
    svc = _make_service(monkeypatch)
    assert svc.max_pixels == MAX_OCR_IMAGE_PIXELS

    fake_img = MagicMock()
    fake_img.__enter__.return_value = fake_img
    fake_img.__exit__.return_value = False
    fake_img.size = (6000, 6000)  # 36,000,000 pixels > 25,000,000
    fake_img.load.side_effect = AssertionError("img.load() must not be called")
    monkeypatch.setattr("app.services.ocr_service.Image.open", lambda _src: fake_img)

    with pytest.raises(OCRProcessingError, match="exceed maximum OCR budget"):
        svc._load_and_validate_image(io.BytesIO(b"fake"))

    fake_img.load.assert_not_called()
    fake_img.__exit__.assert_called_once()


def test_pillow_decompression_bomb_error_maps_to_ocr_processing_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PIL Image.DecompressionBombError maps cleanly to OCRProcessingError."""
    svc = _make_service(monkeypatch)

    def _raise_bomb(_src: object) -> None:
        raise Image.DecompressionBombError("Image size exceeds limit")

    monkeypatch.setattr("app.services.ocr_service.Image.open", _raise_bomb)

    with pytest.raises(OCRProcessingError, match="safe pixel limit"):
        svc._load_and_validate_image(io.BytesIO(b"fake"))


# ── Defect 3: Non-blocking offload & Tesseract timeout handling ──


@pytest.mark.asyncio
async def test_extract_text_from_image_offloads_off_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Blocking Tesseract OCR runs in a worker thread without stalling the event loop."""
    svc = _make_service(monkeypatch, timeout=15.0)
    main_thread_id = threading.get_ident()
    ocr_thread_id: int | None = None
    observed_timeout: float | None = None

    def _slow_ocr(_img: Image.Image, *, config: str, timeout: float) -> str:
        nonlocal ocr_thread_id, observed_timeout
        ocr_thread_id = threading.get_ident()
        observed_timeout = timeout
        time.sleep(0.15)
        return "1. What is virtual memory paging in operating systems?"

    monkeypatch.setattr(
        "app.services.ocr_service.pytesseract.image_to_string",
        _slow_ocr,
    )

    ticks = 0

    async def _ticker(done_event: asyncio.Event) -> None:
        nonlocal ticks
        while not done_event.is_set():
            ticks += 1
            await asyncio.sleep(0.01)

    done = asyncio.Event()
    img = Image.new("RGB", (100, 100), color="white")

    async def _run_ocr() -> object:
        try:
            return await svc.extract_text_from_image(img, preprocess=False)
        finally:
            done.set()

    result, _ = await asyncio.gather(_run_ocr(), _ticker(done))

    assert ocr_thread_id is not None
    assert ocr_thread_id != main_thread_id
    assert observed_timeout == 15.0
    assert ticks >= 3
    assert result is not None


@pytest.mark.asyncio
async def test_extract_from_path_offloads_pdf_processing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """extract_from_path offloads blocking PyMuPDF work via asyncio.to_thread."""
    svc = _make_service(monkeypatch)
    main_thread_id = threading.get_ident()
    direct_thread_id: int | None = None
    pdf_img_thread_id: int | None = None

    def _fake_direct(_path: Path) -> str | None:
        nonlocal direct_thread_id
        direct_thread_id = threading.get_ident()
        return None

    def _fake_pdf_to_img(_path: Path) -> Image.Image:
        nonlocal pdf_img_thread_id
        pdf_img_thread_id = threading.get_ident()
        return Image.new("RGB", (64, 64), color="white")

    monkeypatch.setattr(svc, "_extract_text_from_pdf_direct", _fake_direct)
    monkeypatch.setattr(svc, "_pdf_to_image", _fake_pdf_to_img)
    monkeypatch.setattr(
        "app.services.ocr_service.pytesseract.image_to_string",
        lambda _img, *, config, timeout: (
            "1. Explain semaphore wait and signal operations."
        ),
    )

    result = await svc.extract_from_path(tmp_path / "scan.pdf")

    assert direct_thread_id is not None and direct_thread_id != main_thread_id
    assert pdf_img_thread_id is not None and pdf_img_thread_id != main_thread_id
    assert len(result.questions) == 1


@pytest.mark.asyncio
async def test_tesseract_timeout_maps_runtime_error_to_ocr_processing_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pytesseract RuntimeError timeout is mapped to OCRProcessingError."""
    svc = _make_service(monkeypatch, timeout=2.5)
    seen_timeout: float | None = None

    def _timeout_ocr(_img: Image.Image, *, config: str, timeout: float) -> str:
        nonlocal seen_timeout
        seen_timeout = timeout
        raise RuntimeError("Tesseract process timeout")

    monkeypatch.setattr(
        "app.services.ocr_service.pytesseract.image_to_string",
        _timeout_ocr,
    )

    img = Image.new("RGB", (100, 100), color="white")
    with pytest.raises(OCRProcessingError, match="timed out"):
        await svc.extract_text_from_image(img, preprocess=False)

    assert seen_timeout == 2.5


@pytest.mark.asyncio
async def test_tesseract_error_not_misclassified_as_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pytesseract.TesseractError (a RuntimeError subclass) preserves its failure message."""
    import pytesseract

    svc = _make_service(monkeypatch, timeout=5.0)

    def _tesseract_fail(_img: Image.Image, *, config: str, timeout: float) -> str:
        raise pytesseract.TesseractError(1, "Error opening data file spa.traineddata")

    monkeypatch.setattr(
        "app.services.ocr_service.pytesseract.image_to_string",
        _tesseract_fail,
    )

    img = Image.new("RGB", (100, 100), color="white")
    with pytest.raises(OCRProcessingError) as exc_info:
        await svc.extract_text_from_image(img, preprocess=False)

    msg = str(exc_info.value)
    assert "timed out" not in msg.lower()
    assert "spa.traineddata" in msg
