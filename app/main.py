"""FastAPI application entry point."""

from collections.abc import Sequence
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath
from typing import AsyncGenerator
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

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
# Security middleware — CSRF protection, CORS, and Trusted Host validation
# ---------------------------------------------------------------------------
# Starlette runs middleware in LIFO registration order (last added = outermost).
# Request flow: TrustedHostMiddleware -> CORSMiddleware -> CSRFProtectionMiddleware -> routes.

_CSRF_PROTECTED_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_ALLOWED_FETCH_SITES = frozenset({"same-origin", "same-site", "none"})


def _canonical_origin(raw: str, *, allow_path: bool = False) -> str | None:
    """Normalize an HTTP(S) origin string, returning None for invalid or null values."""
    value = raw.strip()
    if not value or value.lower() == "null":
        return None
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https") or not parsed.netloc:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    if not allow_path and (parsed.path or parsed.query or parsed.fragment):
        return None
    hostname = parsed.hostname
    if not hostname:
        return None
    hostname = hostname.lower()
    host_part = f"[{hostname}]" if ":" in hostname else hostname
    default_port = 80 if scheme == "http" else 443
    if port is None or port == default_port:
        return f"{scheme}://{host_part}"
    return f"{scheme}://{host_part}:{port}"


class CSRFProtectionMiddleware:
    """Defense-in-depth CSRF guard for mutating ``/api/*`` requests.

    Blocks cross-origin drive-by form submissions and empty-body POSTs by
    enforcing Fetch Metadata, Origin/Referer validation, and a non-empty
    ``X-Requested-With`` custom header.
    """

    def __init__(self, app: ASGIApp, allowed_origins: Sequence[str] = ()) -> None:
        self.app = app
        normalized: set[str] = set()
        for origin in allowed_origins:
            if origin == "*":
                continue
            canonical = _canonical_origin(origin)
            if canonical is not None:
                normalized.add(canonical)
        self.allowed_origins = frozenset(normalized)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "").upper()
        path = scope.get("path", "")
        if method not in _CSRF_PROTECTED_METHODS or not (
            path == "/api" or path.startswith("/api/")
        ):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)

        # 1. Fetch Metadata check (when present)
        fetch_sites = headers.getlist("sec-fetch-site")
        if fetch_sites:
            if len(fetch_sites) > 1 or any(
                val.strip().lower() not in _ALLOWED_FETCH_SITES for val in fetch_sites
            ):
                await self._reject(
                    scope,
                    receive,
                    send,
                    "CSRF check failed: disallowed Sec-Fetch-Site header.",
                )
                return

        # Allowed origins for this request: configured CORS origins plus the
        # request's own Host origin (already validated by TrustedHostMiddleware).
        scheme = scope.get("scheme", "http")
        host = headers.get("host", "").strip()
        allowed_for_request = set(self.allowed_origins)
        if host:
            host_origin = _canonical_origin(f"{scheme}://{host}")
            if host_origin is not None:
                allowed_for_request.add(host_origin)

        # 2. Origin check (when present)
        origins = headers.getlist("origin")
        if origins:
            if len(origins) > 1:
                await self._reject(
                    scope,
                    receive,
                    send,
                    "CSRF check failed: multiple Origin headers.",
                )
                return
            origin_canonical = _canonical_origin(origins[0], allow_path=False)
            if origin_canonical is None or origin_canonical not in allowed_for_request:
                await self._reject(
                    scope,
                    receive,
                    send,
                    "CSRF check failed: untrusted Origin header.",
                )
                return
        else:
            # 3. Referer check (when Origin is absent and Referer is present)
            referers = headers.getlist("referer")
            if referers:
                if len(referers) > 1:
                    await self._reject(
                        scope,
                        receive,
                        send,
                        "CSRF check failed: multiple Referer headers.",
                    )
                    return
                referer_canonical = _canonical_origin(referers[0], allow_path=True)
                if (
                    referer_canonical is None
                    or referer_canonical not in allowed_for_request
                ):
                    await self._reject(
                        scope,
                        receive,
                        send,
                        "CSRF check failed: untrusted Referer header.",
                    )
                    return

        # 4. Require non-empty X-Requested-With custom header
        requested_with = headers.get("x-requested-with", "").strip()
        if not requested_with:
            await self._reject(
                scope,
                receive,
                send,
                "CSRF check failed: missing X-Requested-With header.",
            )
            return

        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send, detail: str) -> None:
        response = JSONResponse(status_code=403, content={"detail": detail})
        await response(scope, receive, send)


app.add_middleware(
    CSRFProtectionMiddleware,
    allowed_origins=settings.cors_allowed_origins,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allowed_methods,
    allow_headers=settings.cors_allowed_headers,
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts,
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
    clean_path = path.lstrip("/\\")
    if "\\" in clean_path or any(ord(ch) < 32 for ch in clean_path):
        target = "/"
    else:
        candidate = f"/{clean_path}"
        parsed = urlsplit(candidate)
        target = candidate if not parsed.scheme and not parsed.netloc else "/"
    if request.url.query:
        target += f"?{request.url.query}"
    return RedirectResponse(url=target, status_code=308)


# Built with `bun run build` in frontend/. Mounted last so every API route, the
# docs and /health win; skipped when no build exists so the backend still starts.
_SPA_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _SPA_DIST.is_dir():
    app.mount("/", SPAStaticFiles(directory=_SPA_DIST, html=True), name="spa")
