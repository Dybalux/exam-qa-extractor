"""Bounded chunked reader for multipart UploadFile streams."""

from __future__ import annotations

import logging
from typing import Protocol

from fastapi import HTTPException, status

DEFAULT_CHUNK_SIZE = 64 * 1024  # 64 KiB

_logger = logging.getLogger(__name__)


class AsyncReadableUpload(Protocol):
    """Minimal UploadFile interface required for bounded chunked reading."""

    size: int | None

    async def read(self, size: int = -1) -> bytes: ...


async def read_upload_bounded(
    file: AsyncReadableUpload,
    *,
    max_bytes: int,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    limit_label: str | None = None,
) -> bytes:
    """Read an uploaded file in bounded chunks, aborting with HTTP 413 if too large.

    Checks ``file.size`` before reading any chunk, then reads at most
    ``chunk_size`` bytes per iteration and aborts immediately once the
    accumulated byte count exceeds ``max_bytes`` without consuming the rest
    of the stream.
    """
    if max_bytes < 0:
        raise ValueError("max_bytes must be non-negative")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    label = limit_label or f"{max_bytes} bytes"

    if file.size is not None and file.size > max_bytes:
        _logger.warning(
            "upload rejected: file.size=%d exceeds %d bytes before reading",
            file.size,
            max_bytes,
        )
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Upload exceeds {label} ({file.size} bytes).",
        )

    chunks = bytearray()
    total = 0
    while True:
        # Cap each read so we never buffer more than max_bytes + 1 bytes
        # even when remaining capacity is smaller than chunk_size.
        to_read = min(chunk_size, max_bytes - total + 1)
        chunk = await file.read(to_read)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            _logger.warning(
                "upload rejected: read length=%d exceeds %d bytes (aborted early)",
                total,
                max_bytes,
            )
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Upload exceeds {label}.",
            )
        chunks.extend(chunk)

    return bytes(chunks)
