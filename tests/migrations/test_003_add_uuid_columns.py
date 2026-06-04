"""Tests for the 003_add_uuid_columns Alembic migration.

The 3-step backfill pattern (add nullable -> backfill -> enforce NOT NULL
+ unique) is the migration's contract; these tests assert it.
"""

from __future__ import annotations

import importlib.util
import re
import sqlite3
import sys
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from app.db.base import Base

UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
TABLES = ("exams", "questions", "answers")
TABLES_WITH_COUNTS = [("exams", 3), ("questions", 5), ("answers", 4)]


@pytest.fixture()
def seeded_db(tmp_path: Path) -> Path:
    """Create a SQLite DB at the post-002 state with seed rows."""
    db_path = tmp_path / "seeded.db"
    engine = create_engine(f"sqlite:///{db_path}")
    from app.models.answer import Answer  # noqa: F401
    from app.models.exam import Exam  # noqa: F401
    from app.models.exam_image import ExamImage  # noqa: F401
    from app.models.practice_response import PracticeResponse  # noqa: F401
    from app.models.practice_session import PracticeSession  # noqa: F401
    from app.models.question import Question  # noqa: F401
    Base.metadata.create_all(engine)
    # Mirror 002's net effect: drop the difficulty column. SQLite needs
    # a table rebuild to drop a column referenced by a check constraint.
    # The test simulates the pre-uuid state, so we also drop the uuid
    # column that Base.metadata.create_all just added (the migration
    # under test is what introduces uuid).
    _sqlite3 = sqlite3
    _conn = _sqlite3.connect(str(db_path))
    try:
        _conn.execute("PRAGMA foreign_keys=OFF")
        _conn.executescript("""
            CREATE TABLE questions_new (
                id INTEGER NOT NULL PRIMARY KEY,
                exam_id INTEGER NOT NULL,
                image_id INTEGER,
                question_text TEXT NOT NULL,
                extracted_text TEXT,
                confidence_score FLOAT,
                topic VARCHAR(50) NOT NULL,
                order_in_exam INTEGER,
                is_corrected BOOLEAN NOT NULL,
                correction_notes TEXT,
                has_code_in_answers BOOLEAN NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE,
                FOREIGN KEY(image_id) REFERENCES exam_images(id) ON DELETE SET NULL,
                CHECK (order_in_exam BETWEEN 1 AND 50)
            );
            INSERT INTO questions_new
            SELECT id, exam_id, image_id, question_text, extracted_text,
                   confidence_score, topic, order_in_exam, is_corrected,
                   correction_notes, has_code_in_answers, created_at, updated_at
            FROM questions;
            DROP TABLE questions;
            ALTER TABLE questions_new RENAME TO questions;
            CREATE INDEX idx_question_exam ON questions(exam_id);
            CREATE INDEX idx_question_topic ON questions(topic);
            CREATE INDEX idx_question_corrected ON questions(is_corrected);

            -- Drop the uuid columns the model just created; the
            -- migration under test is what introduces them.
            CREATE TABLE exams_new (
                id INTEGER NOT NULL PRIMARY KEY,
                partial_number INTEGER NOT NULL,
                exam_date DATE,
                topic_tags TEXT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                CHECK (partial_number IN (1, 2, 3, 4))
            );
            INSERT INTO exams_new
            SELECT id, partial_number, exam_date, topic_tags, created_at, updated_at
            FROM exams;
            DROP TABLE exams;
            ALTER TABLE exams_new RENAME TO exams;
            CREATE INDEX idx_exam_partial ON exams(partial_number);
            CREATE INDEX idx_exam_date ON exams(exam_date);

            CREATE TABLE answers_new (
                id INTEGER NOT NULL PRIMARY KEY,
                question_id INTEGER NOT NULL,
                answer_text TEXT NOT NULL,
                answer_type VARCHAR(20) NOT NULL,
                is_common_misconception BOOLEAN NOT NULL,
                explanation TEXT,
                display_order INTEGER NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE,
                CHECK (answer_type IN ('correct', 'incorrect', 'partial'))
            );
            INSERT INTO answers_new
            SELECT id, question_id, answer_text, answer_type,
                   is_common_misconception, explanation, display_order,
                   created_at, updated_at
            FROM answers;
            DROP TABLE answers;
            ALTER TABLE answers_new RENAME TO answers;
            CREATE INDEX idx_answer_question ON answers(question_id);
            CREATE INDEX idx_answer_type ON answers(answer_type);
        """)
    finally:
        _conn.execute("PRAGMA foreign_keys=ON")
        _conn.close()

    # Seed: 3 exams, 5 questions, 4 answers. The schema is the
    # pre-uuid (post-002) state, so the INSERTs omit the uuid column
    # — the migration under test adds it and backfills.
    with engine.begin() as conn:
        for p in (1, 2, 3):
            conn.execute(
                text("INSERT INTO exams (partial_number, exam_date, topic_tags, "
                     "created_at, updated_at) VALUES (:p, NULL, NULL, :ts, :ts)"),
                {"p": p, "ts": "2026-06-03 00:00:00"},
            )
        for i in range(1, 6):
            conn.execute(
                text("INSERT INTO questions (exam_id, image_id, question_text, "
                     "extracted_text, confidence_score, topic, order_in_exam, "
                     "is_corrected, correction_notes, has_code_in_answers, "
                     "created_at, updated_at) "
                     "VALUES (1, NULL, :t, NULL, NULL, 'OTHER', :o, 0, NULL, 0, :ts, :ts)"),
                {"t": f"Q{i}", "o": i, "ts": "2026-06-03 00:00:00"},
            )
        for q_id, ans in [(1, "A"), (2, "B"), (3, "C"), (4, "D")]:
            conn.execute(
                text("INSERT INTO answers (question_id, answer_text, answer_type, "
                     "is_common_misconception, explanation, display_order, "
                     "created_at, updated_at) "
                     "VALUES (:q, :a, 'correct', 0, NULL, 0, :ts, :ts)"),
                {"q": q_id, "a": ans, "ts": "2026-06-03 00:00:00"},
            )
    engine.dispose()
    return db_path


def _load_migration_module():
    """Load 003_add_uuid_columns.py by file path so the local alembic/
    source directory cannot shadow the installed alembic package."""
    path = (Path(__file__).resolve().parent.parent.parent
            / "alembic" / "versions" / "003_add_uuid_columns.py")
    spec = importlib.util.spec_from_file_location("migration_003_under_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run_migration(module, fn_name: str, db_path: Path) -> None:
    """Run the migration's upgrade()/downgrade() in a private transaction."""
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        ctx = MigrationContext.configure(connection)
        with Operations.context(ctx):
            getattr(module, fn_name)()
    engine.dispose()


def _assert_uuid_state(db_path: Path, table: str, expected_count: int) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE uuid IS NULL"
        ).fetchone()[0] == 0
        assert conn.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0] == expected_count
        uuids = [u for (u,) in conn.execute(f"SELECT uuid FROM {table}").fetchall()]
        assert all(UUID4_RE.match(u) for u in uuids)
        dups = conn.execute(
            f"SELECT uuid, COUNT(*) FROM {table} GROUP BY uuid HAVING COUNT(*) > 1"
        ).fetchall()
        assert dups == []
    finally:
        conn.close()


def test_migration_upgrade_assigns_uuid_to_every_row(seeded_db: Path) -> None:
    """upgrade() assigns a unique non-null uuid to every existing row."""
    module = _load_migration_module()
    _run_migration(module, "upgrade", seeded_db)

    for table, expected in TABLES_WITH_COUNTS:
        _assert_uuid_state(seeded_db, table, expected)

    # Unique index exists on each table.
    conn = sqlite3.connect(str(seeded_db))
    try:
        for table in TABLES:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                f"AND tbl_name='{table}' AND name='ix_{table}_uuid'"
            ).fetchall()
            assert rows, f"missing unique index ix_{table}_uuid"
    finally:
        conn.close()


def test_migration_downgrade_reverses_cleanly(seeded_db: Path) -> None:
    """downgrade() drops the uuid column + index with no other data loss."""
    module = _load_migration_module()
    _run_migration(module, "upgrade", seeded_db)
    _run_migration(module, "downgrade", seeded_db)

    conn = sqlite3.connect(str(seeded_db))
    try:
        for table, expected in TABLES_WITH_COUNTS:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            assert "uuid" not in cols
            idx = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                f"AND tbl_name='{table}' AND name='ix_{table}_uuid'"
            ).fetchall()
            assert idx == []
            assert conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0] == expected
    finally:
        conn.close()


def test_backfill_only_fills_null_rows(seeded_db: Path) -> None:
    """Step 2's UPDATE has `WHERE uuid IS NULL`: a partial-backfill state
    is safely completed without overwriting existing uuids."""
    # Pre-add the column with one row pre-filled.
    engine = create_engine(f"sqlite:///{seeded_db}")
    with engine.begin() as conn:
        for table in TABLES:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN uuid VARCHAR(36)"))
        conn.execute(
            text("UPDATE exams SET uuid = '11111111-1111-4111-8111-111111111111' WHERE id = 1")
        )
    engine.dispose()

    # Run only the backfill helper (the full upgrade() cannot re-run step 1).
    module = _load_migration_module()
    engine = create_engine(f"sqlite:///{seeded_db}")
    with engine.begin() as connection:
        ctx = MigrationContext.configure(connection)
        with Operations.context(ctx):
            for table in module.UPGRADE_ORDER:
                module._backfill_uuid_column(table)
    engine.dispose()

    conn = sqlite3.connect(str(seeded_db))
    try:
        row = conn.execute("SELECT uuid FROM exams WHERE id = 1").fetchone()
        assert row[0] == "11111111-1111-4111-8111-111111111111"
        others = [u for (u,) in conn.execute(
            "SELECT uuid FROM exams WHERE id != 1"
        ).fetchall()]
        assert all(UUID4_RE.match(u) for u in others)
        for table in TABLES:
            assert conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE uuid IS NULL"
            ).fetchone()[0] == 0
    finally:
        conn.close()
