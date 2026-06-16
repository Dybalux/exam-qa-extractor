"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.api.pages import router as pages_router
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
    return JSONResponse(status_code=409, content={"detail": exc.message, "extra": exc.details})


@app.exception_handler(ValidationError)
async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.message, "extra": exc.details})


@app.exception_handler(FileValidationError)
async def file_validation_handler(request: Request, exc: FileValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.message, "extra": exc.details})


@app.exception_handler(OCRProcessingError)
async def ocr_handler(request: Request, exc: OCRProcessingError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.message, "extra": exc.details})


@app.exception_handler(StorageError)
async def storage_handler(request: Request, exc: StorageError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": exc.message})


@app.exception_handler(MalformedImportError)
async def malformed_import_handler(request: Request, exc: MalformedImportError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.message, "validation_errors": exc.details})


@app.exception_handler(UnknownSchemaVersion)
async def unknown_schema_handler(request: Request, exc: UnknownSchemaVersion) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.message})


@app.exception_handler(PayloadTooLargeError)
async def payload_too_large_handler(request: Request, exc: PayloadTooLargeError) -> JSONResponse:
    return JSONResponse(status_code=413, content={"detail": exc.message})


@app.exception_handler(ExamStudyError)
async def generic_domain_handler(request: Request, exc: ExamStudyError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": exc.message})


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(pages_router)                          # HTML views (no prefix)
app.include_router(api_router, prefix="/api/v1")          # JSON API


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Liveness probe."""
    return {"status": "ok", "version": "0.1.0"}
