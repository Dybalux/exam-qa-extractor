"""Drop the deprecated questions.topic column and enforce NOT NULL constraints.

This migration completes the topic domain refactoring by:
1. Dropping the legacy ``questions.topic`` string column (SQLite requires table
   rebuild — batch_alter_table with recreate='always' handles this).
2. Setting ``questions.topic_id`` to NOT NULL (all rows were backfilled by
   migration 004).
3. Setting ``exams.subject_id`` to NOT NULL (all rows were backfilled by
   migration 004).

The downgrade path restores the ``topic`` column, drops the NOT NULL
constraints, and removes the indexes.

Revision ID: 005_drop_topic_column
Revises: 004_add_subjects_topics
Create Date: 2026-06-30 23:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "005_drop_topic_column"
down_revision = "004_add_subjects_topics"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    """Check whether *column* exists in *table*."""
    conn = op.get_bind()
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return column in {row[1] for row in rows}


def _index_exists(name: str) -> bool:
    """Check whether an index named *name* exists."""
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='index' AND name = :name"),
        {"name": name},
    ).first()
    return row is not None


def _verify_backfill(table: str, column: str) -> None:
    """Raise an error if any row in *table* has NULL in *column*."""
    conn = op.get_bind()
    nulls = conn.execute(
        sa.text(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL")
    ).scalar()
    if (nulls or 0) > 0:
        raise RuntimeError(
            f"Cannot apply migration: {nulls} row(s) in '{table}' "
            f"have NULL in '{column}'. Run migration 004 first to backfill."
        )


def upgrade() -> None:
    """Drop topic column, enforce NOT NULL on FK columns."""
    # -- Verify backfills before making destructive changes ----
    _verify_backfill("questions", "topic_id")
    _verify_backfill("exams", "subject_id")

    # -- Drop idx_question_topic index (covers the removed column) ----
    if _index_exists("idx_question_topic"):
        op.drop_index("idx_question_topic", table_name="questions")

    # -- Rebuild questions table without the 'topic' column ----
    # recreate='always' forces a full table rebuild (CREATE new, COPY data,
    # DROP old, RENAME). This is required for column drops in SQLite < 3.35.
    if _column_exists("questions", "topic"):
        with op.batch_alter_table("questions", recreate="always") as batch_op:
            batch_op.drop_column("topic")

    # -- Enforce NOT NULL on questions.topic_id ----
    with op.batch_alter_table("questions", schema=None) as batch_op:
        batch_op.alter_column("topic_id", nullable=False)

    # -- Enforce NOT NULL on exams.subject_id ----
    with op.batch_alter_table("exams", schema=None) as batch_op:
        batch_op.alter_column("subject_id", nullable=False)


def downgrade() -> None:
    """Restore the topic column and relax NOT NULL constraints."""
    # -- Relax NOT NULL constraints ----
    with op.batch_alter_table("questions", schema=None) as batch_op:
        batch_op.alter_column("topic_id", nullable=True)

    with op.batch_alter_table("exams", schema=None) as batch_op:
        batch_op.alter_column("subject_id", nullable=True)

    # -- Restore the topic column ----
    if not _column_exists("questions", "topic"):
        with op.batch_alter_table("questions", recreate="always") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "topic", sa.String(50), nullable=False, server_default="other"
                )
            )

    # -- Recreate idx_question_topic index ----
    if not _index_exists("idx_question_topic"):
        op.create_index("idx_question_topic", "questions", ["topic"])
