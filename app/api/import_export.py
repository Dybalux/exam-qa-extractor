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
import logging
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.core.exceptions import (
    MalformedImportError,
    PayloadTooLargeError,
    UnknownSchemaVersion,
)
from app.dependencies import get_json_io_service
from app.schemas.json_io import (
    ImportApplyResultSchema,
    ImportPreviewSchema,
)
from app.services.json_io_service import JsonIOService

router = APIRouter()

# The endpoint logger mirrors the service's exact-string convention so
# log filters key on a single name across the import/export flow.
_logger = logging.getLogger("app.api.import_export")


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
    body = json.dumps(envelope.model_dump(mode="json"), default=str).encode("utf-8")
    filename = f"exam-backup-{datetime.now().strftime('%Y%m%d')}.json"
    return StreamingResponse(
        iter([body]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/import",
    status_code=200,
    response_model=ImportPreviewSchema | ImportApplyResultSchema,
)
async def import_envelope(
    response: Response,
    file: UploadFile = File(...),
    confirm: bool = Query(default=False),
    svc: JsonIOService = Depends(get_json_io_service),
) -> ImportPreviewSchema | ImportApplyResultSchema | JSONResponse:
    """Import a JSON envelope (multipart file upload).

    This is the **safety boundary** for the entire export/import flow.
    Three responsibilities, in this order:

    1. **Size cap (BEFORE any parse).** Belt-and-suspenders: the
       ``file.size`` attribute is checked (when present) AND the
       actual read length is compared against
       ``settings.max_import_size_mb * 1024 * 1024``. Either check
       tripping raises 413 BEFORE any JSON parse happens. Sending a
       deliberately-malformed-but-oversize payload yields 413, NOT
       400 (the parse is never reached).

    2. **JSON parse.** A non-JSON body yields 400 with the parser
       error message in ``detail``. Other parse-level issues (e.g.
       top-level not a dict) are mapped to 400 as well.

    3. **Service dispatch with ``?confirm=true`` gate.**

       * **Without** ``?confirm=true`` (default): call
         :meth:`JsonIOService.preview_import` and return 200 with
         :class:`ImportPreviewSchema`. The DB is NOT touched. This
         is the safe default — the dashboard's "Vista previa" button
         is always a read.

       * **With** ``?confirm=true``: call
         :meth:`JsonIOService.apply_import` and return 201 with
         :class:`ImportApplyResultSchema`. This is the **destructive
         path**; the service wraps it in a single transaction with
         automatic rollback on any error.

    Exception mapping
    -----------------

    * :class:`MalformedImportError` (the service collected Pydantic
      errors across every entry) → 400 with body
      ``{"detail": "Malformed import", "validation_errors": [...]}``.
      The ``validation_errors`` array is in the BODY, not a custom
      header — the dashboard JS handler reads it directly to render
      the per-entry error list.
    * :class:`UnknownSchemaVersion` → 400 with the service's message
      (which includes both the offending version and the supported
      set).
    * :class:`PayloadTooLargeError` → 413 (defensive; the size check
      above uses ``HTTPException(413)`` directly).
    * :class:`sqlalchemy.exc.IntegrityError` (mid-apply FK fail,
      etc.) → 500. The service has already rolled back the
      transaction; the HTTP layer just surfaces the failure.
    """
    settings = get_settings()
    max_bytes = settings.max_import_size_mb * 1024 * 1024

    # 1. Read the upload body. We must read to enforce the
    #    belt-and-suspenders size check, since ``file.size`` can be
    #    ``None`` for some multipart sources.
    raw = await file.read()
    if file.size is not None and file.size > max_bytes:
        _logger.warning(
            "import rejected: file.size=%d exceeds %d bytes (pre-parse)",
            file.size,
            max_bytes,
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Upload exceeds {settings.max_import_size_mb} MB ({file.size} bytes)."
            ),
        )
    if len(raw) > max_bytes:
        _logger.warning(
            "import rejected: read length=%d exceeds %d bytes (pre-parse)",
            len(raw),
            max_bytes,
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Upload exceeds {settings.max_import_size_mb} MB ({len(raw)} bytes)."
            ),
        )

    # 2. Parse JSON. A parse error here yields 400 with the parser
    #    message in ``detail`` (we never reach the service).
    try:
        json_data = json.loads(raw)
    except json.JSONDecodeError as exc:
        _logger.warning("import rejected: unparseable JSON: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON: {exc}",
        ) from exc
    if not isinstance(json_data, dict):
        # The export envelope is a top-level dict; anything else is
        # a structural error that the service would also reject, but
        # we surface it here with a cleaner message.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Import payload must be a JSON object "
                f"(got {type(json_data).__name__})."
            ),
        )

    # 3. Service dispatch. The service raises the typed exceptions;
    #    we map them to HTTP responses here.
    try:
        if confirm:
            result = await svc.apply_import(json_data)
            _logger.info(
                "import applied: created=%d updated=%d deleted=%d",
                result.created,
                result.updated,
                result.deleted,
            )
            # The plan locks the apply response at 201 (created /
            # applied). The route's default is 200; we override per-
            # response via the ``Response`` parameter.
            if response is not None:
                response.status_code = status.HTTP_201_CREATED
            return result
        else:
            preview = await svc.preview_import(json_data)
            _logger.info(
                "import preview: to_create=%d to_update=%d to_delete=%d",
                preview.to_create,
                preview.to_update,
                preview.to_delete,
            )
            return preview
    except MalformedImportError as exc:
        _logger.warning(
            "import rejected: %d malformed entries",
            len(exc.details.get("validation_errors", [])),
        )
        # The 400 body shape is the contract: ``detail`` is a
        # human-readable summary, ``validation_errors`` is the array
        # the JS handler renders in the modal. We MUST return a
        # ``JSONResponse`` directly because FastAPI's ``HTTPException``
        # wraps a dict ``detail`` in another ``{"detail": ...}``
        # envelope, breaking the flat shape the plan requires.
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": "Malformed import",
                "validation_errors": exc.details.get("validation_errors", []),
            },
        )
    except UnknownSchemaVersion as exc:
        _logger.warning("import rejected: %s", exc.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc
    except PayloadTooLargeError as exc:
        # Defensive: the size check above uses ``HTTPException(413)``
        # directly. If the service ever raises this, map it the same
        # way.
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=exc.message,
        ) from exc
    except IntegrityError as exc:
        # The service's ``apply_import`` runs in a single transaction;
        # any ``IntegrityError`` (e.g. dangling ``image_id`` FK in a
        # cross-DB import) triggers an automatic rollback. The HTTP
        # layer surfaces the failure with 500 — the DB is unchanged.
        _logger.error("import failed: IntegrityError: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal import error (DB constraint violation).",
        ) from exc
