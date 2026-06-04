"""Import/Export API routes.

Thin HTTP layer over :class:`~app.services.json_io_service.JsonIOService`.
The service layer owns the export envelope shape, the diff semantics and
the atomicity contract for import. This module only:

* Maps the service's :class:`ExportFileSchema` to a streaming JSON
  download with a date-stamped filename.
* (PR 3b / T3.2) Maps the import multipart upload to the service's
  ``preview_import`` / ``apply_import`` flow with a ``?confirm=true``
  gate, a pre-parse size cap and the canonical 400 body shape for
  :class:`~app.core.exceptions.MalformedImportError`.

The router is mounted with an empty prefix in :mod:`app.api` so the
final URLs are ``/api/v1/export`` and ``/api/v1/import`` (the
``/api/v1`` prefix comes from :mod:`app.main`, not the file location).
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.dependencies import get_json_io_service
from app.services.json_io_service import JsonIOService

router = APIRouter()


@router.post("/export", status_code=200)
async def export_full_db(
    svc: JsonIOService = Depends(get_json_io_service),
) -> StreamingResponse:
    """Stream the full DB as a date-stamped JSON download.

    Returns 200 with:

    * ``Content-Type: application/json``
    * ``Content-Disposition: attachment; filename="exam-backup-YYYYMMDD.json"``
    * Body: the export envelope (``schema_version``, ``exported_at``,
      denormalized ``questions`` with nested ``exam_context`` and
      ``answers``), serialized via
      ``envelope.model_dump(mode="json")`` with ``default=str`` so any
      non-JSON-native field (e.g. ``datetime``) falls back to its
      string representation.

    The body is wrapped in a :class:`StreamingResponse` whose
    ``iter([body])`` is a single-chunk iterable — the streaming shape
    is preserved without falling back to ``BytesIO`` + ``seek`` (which
    would defeat the streaming contract by materializing the full body
    in memory twice).
    """
    envelope = await svc.export_full_db()
    body = json.dumps(
        envelope.model_dump(mode="json"), default=str
    ).encode("utf-8")
    filename = f"exam-backup-{datetime.now().strftime('%Y%m%d')}.json"
    return StreamingResponse(
        iter([body]),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@router.post("/import")
async def import_full_db() -> None:
    """Import endpoint stub — implemented in PR 3b (T3.2).

    The full ``POST /api/v1/import?confirm=true`` flow (multipart
    upload, pre-parse size cap, preview/confirm gate, 400 body shape
    for :class:`~app.core.exceptions.MalformedImportError`) is
    delivered in the next chained PR. The route is registered here so
    the URL contract is consistent across PR 3a, PR 3b and the
    dashboard wiring (T3.3 / T3.4) — the dashboard button can already
    target ``/api/v1/import`` in this PR's UI work without changing
    the URL later.
    """
    raise HTTPException(
        status_code=501,
        detail="Import endpoint is not yet implemented (PR 3b / T3.2).",
    )
