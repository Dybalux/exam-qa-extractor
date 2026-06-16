"""Shared pytest fixtures for the exam-qa-extractor test suite.

These fixtures are designed to be used across all PRs of the
`exam-export-import` change. They provide:

- A clean in-memory async SQLite database per test (function scope).
- An async session bound to that engine.
- A FastAPI `TestClient`-style async client via httpx + ASGITransport.

Notes on isolation:
- We use a single in-memory SQLite database shared via a connection
  pool for the duration of one test, so multiple sessions can see
  the same data. After the test, the engine is disposed and the
  in-memory store is gone.
- We import the FastAPI app lazily inside the fixture so the test
  collection step doesn't fail if the app is broken.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

# The project ships an `alembic/` source directory that shadows the
# installed `alembic` package. Both the bare project root and the
# empty-string `""` (cwd) entry on sys.path resolve to it. Remove any
# sys.path entry that resolves to the project root, then promote the
# installed alembic parent to the front.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path[:] = [
    p
    for p in sys.path
    if p
    and not (p == _PROJECT_ROOT or str(Path(p).resolve()) == _PROJECT_ROOT)
]

# Now find the real alembic package and prepend its parent.
for _entry in sys.path:
    if not _entry:
        continue
    _candidate = Path(_entry) / "alembic" / "__init__.py"
    if _candidate.is_file() and str(Path(_entry).resolve()) != _PROJECT_ROOT:
        # Promote to front of path.
        if _entry in sys.path:
            sys.path.remove(_entry)
        sys.path.insert(0, _entry)
        break

# Re-add project root at the END so 'import app' resolves correctly.
# The installed alembic (at position 0) takes precedence over project's
# alembic/ dir; app/ is only in the project root so this is safe.
if _PROJECT_ROOT not in sys.path:
    sys.path.append(_PROJECT_ROOT)

# Drop any cached `alembic` modules.
for _name in [n for n in list(sys.modules) if n == "alembic" or n.startswith("alembic.")]:
    sys.modules.pop(_name, None)
importlib.invalidate_caches()

# Pre-load alembic from the installed package so the conftest guarantees
# it's cached under the correct path before any test module imports.
import alembic  # noqa: E402  (intentional late import after path fix)

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Importing the models here is required so they register with
# ``app.db.base.Base`` before the ``db_engine`` fixture calls
# ``Base.metadata.create_all``. Without this, the in-memory test
# database has no tables and every endpoint that touches the DB
# raises "no such table: exams". The HTTP-using tests in
# ``tests/api/`` used to import the models themselves; with this
# conftest-level import, the ``client`` fixture works for any
# test that uses it without each test having to remember the
# import.
from app.models import Answer  # noqa: F401
from app.models import Exam  # noqa: F401
from app.models import Question  # noqa: F401
from app.db.base import Base


@pytest_asyncio.fixture
async def db_engine():
    """Provide a fresh in-memory async SQLite engine per test.

    Using a shared in-memory db (via `StaticPool`-style engine) so
    multiple sessions can see the same data within a single test. The
    engine is disposed at teardown, releasing the in-memory store.

    Foreign-key enforcement is enabled per connection via a sync
    event listener. SQLite ships with FK enforcement OFF by default;
    without this pragma, tests that rely on FK violations (e.g.
    ``test_apply_rolls_back_on_missing_image_id_fk``) would not
    trigger ``IntegrityError`` and the rollback safety net would be
    untestable.
    """
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        """Run ``PRAGMA foreign_keys = ON`` on every new DBAPI connection."""
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
        finally:
            cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async session bound to the test engine."""
    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx async client wired to the FastAPI app.

    The app's get_db dependency is overridden to yield sessions from
    the test engine, so HTTP requests operate on the same in-memory
    database the rest of the test sees.
    """
    from app.dependencies import get_db
    from app.main import app

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
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)
