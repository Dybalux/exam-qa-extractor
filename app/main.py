"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import api_router
from app.config import get_settings
from app.core.exceptions import (
    ConflictError,
    ExamStudyError,
    FileValidationError,
    MalformedImportError,
    NotFoundError,
    OCRProcessingError,
    PayloadTooLargeError,
    StorageError,
    UnknownSchemaVersion,
    ValidationError,
)
from app.db.init_db import create_tables

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize the database on startup."""
    await create_tables()
    yield


app = FastAPI(
    title="Exam Study System",
    description=(
        "OCR-powered API to extract questions from exam images, "
        "manage answers, and run interactive practice sessions."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allowed_methods,
    allow_headers=settings.cors_allowed_headers,
)

# ---------------------------------------------------------------------------
# Exception handlers — map domain errors to HTTP status codes
# ---------------------------------------------------------------------------


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.message})


@app.exception_handler(ConflictError)
async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(
        status_code=409, content={"detail": exc.message, "extra": exc.details}
    )


@app.exception_handler(ValidationError)
async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422, content={"detail": exc.message, "extra": exc.details}
    )


@app.exception_handler(FileValidationError)
async def file_validation_handler(
    request: Request, exc: FileValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422, content={"detail": exc.message, "extra": exc.details}
    )


@app.exception_handler(OCRProcessingError)
async def ocr_handler(request: Request, exc: OCRProcessingError) -> JSONResponse:
    return JSONResponse(
        status_code=422, content={"detail": exc.message, "extra": exc.details}
    )


@app.exception_handler(StorageError)
async def storage_handler(request: Request, exc: StorageError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": exc.message})


@app.exception_handler(MalformedImportError)
async def malformed_import_handler(
    request: Request, exc: MalformedImportError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": exc.message, "validation_errors": exc.details},
    )


@app.exception_handler(UnknownSchemaVersion)
async def unknown_schema_handler(
    request: Request, exc: UnknownSchemaVersion
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.message})


@app.exception_handler(PayloadTooLargeError)
async def payload_too_large_handler(
    request: Request, exc: PayloadTooLargeError
) -> JSONResponse:
    return JSONResponse(status_code=413, content={"detail": exc.message})


@app.exception_handler(ExamStudyError)
async def generic_domain_handler(request: Request, exc: ExamStudyError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": exc.message})


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(api_router, prefix="/api/v1")  # JSON API


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Liveness probe."""
    return {"status": "ok", "version": "0.1.0"}


# ---------------------------------------------------------------------------
# React SPA (served at the site root)
# ---------------------------------------------------------------------------

# Paths owned by the backend. They must never fall back to index.html: an
# unknown /api/... URL has to stay a real 404 for API clients.
_BACKEND_ROOTS = {"api", "docs", "redoc", "openapi.json", "health"}


class SPAStaticFiles(StaticFiles):
    """StaticFiles that falls back to index.html for client-side routes.

    Only extension-less paths (``/practice/3``) fall back; a missing asset such
    as ``/missing.js`` keeps its real 404, and so does anything under the
    backend-owned roots in ``_BACKEND_ROOTS``.
    """

    async def get_response(self, path: str, scope):  # type: ignore[no-untyped-def]
        no_fallback = (
            bool(PurePosixPath(path).suffix) or path.split("/", 1)[0] in _BACKEND_ROOTS
        )
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or no_fallback:
                raise
            return await super().get_response("index.html", scope)
        if response.status_code == 404 and not no_fallback:
            return await super().get_response("index.html", scope)
        return response


@app.get("/app", include_in_schema=False)
@app.get("/app/{path:path}", include_in_schema=False)
async def legacy_app_prefix(request: Request, path: str = "") -> RedirectResponse:
    """Old SPA URLs lived under /app; send them to the same path at the root."""
    target = f"/{path}"
    if request.url.query:
        target += f"?{request.url.query}"
    return RedirectResponse(url=target, status_code=308)


# Built with `bun run build` in frontend/. Mounted last so every API route, the
# docs and /health win; skipped when no build exists so the backend still starts.
_SPA_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _SPA_DIST.is_dir():
    app.mount("/", SPAStaticFiles(directory=_SPA_DIST, html=True), name="spa")
