"""Add subjects and topics tables, seed default data, backfill questions and exams.

This migration introduces the dynamic topic domain:
1. Create subjects and topics tables (IF NOT EXISTS — they may already exist
   from Base.metadata.create_all() after Phase 1 model changes).
2. Seed the default "Sistemas Operativos" subject and nine OS topics
   (processes, memory, files, scheduling, deadlock, synchronization, io,
   security, other).
3. Add topic_id column to questions, backfill from the legacy topic string
   column, and create an index.
4. Add subject_id column to exams, backfill to the default subject, and
   create an index.

The backfill is re-runnable: UPDATE only touches rows where the target
column is still NULL, so a partial run can be resumed safely.

Revision ID: 004_add_subjects_topics
Revises: 003_add_uuid_columns
Create Date: 2026-06-30 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "004_add_subjects_topics"
down_revision = "003_add_uuid_columns"
branch_labels = None
depends_on = None

# Default subject slug used for backfill and seeding.
DEFAULT_SUBJECT_SLUG = "sistemas-operativos"
DEFAULT_SUBJECT_NAME = "Sistemas Operativos"

# OS topics seeded from the legacy TopicEnum. Each tuple is (slug, display_name).
OS_TOPICS: list[tuple[str, str]] = [
    ("processes", "Procesos"),
    ("memory", "Administración de Memoria"),
    ("files", "Sistemas de Archivos"),
    ("scheduling", "Planificación de CPU"),
    ("deadlock", "Deadlock"),
    ("synchronization", "Sincronización"),
    ("io", "Entrada/Salida"),
    ("security", "Seguridad"),
    ("other", "Otros"),
]


def _table_exists(table: str) -> bool:
    """Check whether *table* exists in the current database."""
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name = :table"),
        {"table": table},
    ).first()
    return row is not None


def _seed_subject(conn, uuid_str: str) -> int | None:
    """Insert the default subject if not present. Returns its id or None."""
    existing = conn.execute(
        sa.text("SELECT id FROM subjects WHERE slug = :slug"),
        {"slug": DEFAULT_SUBJECT_SLUG},
    ).first()
    if existing:
        return existing[0]
    conn.execute(
        sa.text(
            "INSERT INTO subjects (uuid, name, slug, created_at, updated_at) "
            "VALUES (:uuid, :name, :slug, datetime('now'), datetime('now'))"
        ),
        {"uuid": uuid_str, "name": DEFAULT_SUBJECT_NAME, "slug": DEFAULT_SUBJECT_SLUG},
    )
    row = conn.execute(
        sa.text("SELECT id FROM subjects WHERE slug = :slug"),
        {"slug": DEFAULT_SUBJECT_SLUG},
    ).first()
    return row[0] if row else None


def _seed_topics(conn, subject_id: int) -> None:
    """Insert OS topics linked to *subject_id*, skipping those that already exist."""
    import uuid as _uuid

    for slug, display_name in OS_TOPICS:
        existing = conn.execute(
            sa.text("SELECT id FROM topics WHERE slug = :slug"),
            {"slug": slug},
        ).first()
        if existing:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO topics (uuid, name, slug, subject_id, created_at, updated_at) "
                "VALUES (:uuid, :name, :slug, :subject_id, datetime('now'), datetime('now'))"
            ),
            {
                "uuid": str(_uuid.uuid4()),
                "name": display_name,
                "slug": slug,
                "subject_id": subject_id,
            },
        )


def _backfill_topic_id(conn) -> None:
    """Set questions.topic_id by matching questions.topic to topics.slug.

    Only updates rows where topic_id IS NULL, making the operation re-runnable.
    """
    conn.execute(
        sa.text(
            "UPDATE questions SET topic_id = ("
            "  SELECT topics.id FROM topics "
            "  WHERE topics.slug = questions.topic"
            ") "
            "WHERE topic_id IS NULL"
        )
    )


def _backfill_subject_id(conn, subject_id: int) -> None:
    """Set exams.subject_id to *subject_id* for rows where it is still NULL."""
    conn.execute(
        sa.text("UPDATE exams SET subject_id = :subject_id WHERE subject_id IS NULL"),
        {"subject_id": subject_id},
    )


def upgrade() -> None:
    """Create tables, seed data, add columns, backfill."""
    import uuid as _uuid

    conn = op.get_bind()

    # 1. Ensure subjects table exists (may have been created by create_all()).
    if not _table_exists("subjects"):
        op.create_table(
            "subjects",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("uuid", sa.String(36), unique=True, index=True, nullable=False),
            sa.Column("name", sa.String(100), unique=True, nullable=False),
            sa.Column("slug", sa.String(100), unique=True, index=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    # 2. Ensure topics table exists.
    if not _table_exists("topics"):
        op.create_table(
            "topics",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("uuid", sa.String(36), unique=True, index=True, nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("slug", sa.String(100), unique=True, index=True, nullable=False),
            sa.Column(
                "subject_id",
                sa.Integer(),
                sa.ForeignKey("subjects.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    # 3. Seed default subject.
    subject_uuid = str(_uuid.uuid4())
    subject_id = _seed_subject(conn, subject_uuid)

    # 4. Seed topics.
    _seed_topics(conn, subject_id)

    # 5. Add topic_id column to questions.
    if "topic_id" not in _existing_columns("questions"):
        with op.batch_alter_table("questions", schema=None) as batch_op:
            batch_op.add_column(sa.Column("topic_id", sa.Integer(), nullable=True))
        _backfill_topic_id(conn)

    # 6. Add subject_id column to exams.
    if "subject_id" not in _existing_columns("exams"):
        with op.batch_alter_table("exams", schema=None) as batch_op:
            batch_op.add_column(sa.Column("subject_id", sa.Integer(), nullable=True))
        _backfill_subject_id(conn, subject_id)

    # 7. Create indexes on the new FK columns.
    _create_index_if_missing("questions", "topic_id")
    _create_index_if_missing("exams", "subject_id")


def _existing_columns(table: str) -> set[str]:
    """Return the set of column names present in *table*."""
    conn = op.get_bind()
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def _create_index_if_missing(table: str, column: str) -> None:
    """Create an index on *table*.*column* if it does not already exist."""
    conn = op.get_bind()
    idx_name = f"ix_{table}_{column}"
    existing = conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='index' AND name = :name"),
        {"name": idx_name},
    ).first()
    if not existing:
        op.create_index(idx_name, table, [column])


def downgrade() -> None:
    """Remove topic_id and subject_id columns, drop topics and subjects tables."""
    # Drop indexes first.
    with op.batch_alter_table("questions", schema=None) as batch_op:
        batch_op.drop_index("ix_questions_topic_id")
        batch_op.drop_column("topic_id")

    with op.batch_alter_table("exams", schema=None) as batch_op:
        batch_op.drop_index("ix_exams_subject_id")
        batch_op.drop_column("subject_id")

    # Drop tables in FK order (children first).
    if _table_exists("topics"):
        op.drop_table("topics")

    if _table_exists("subjects"):
        op.drop_table("subjects")
