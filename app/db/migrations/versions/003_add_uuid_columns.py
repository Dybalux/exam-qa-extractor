"""Add uuid columns to exams, questions, and answers (3-step backfill).

HIGHEST-RISK MIGRATION IN THE EXAM-EXPORT-IMPORT CHANGE.
DO NOT "SIMPLIFY" THE 3-STEP PATTERN. The reasons:

1. SQLite does NOT support adding a NOT NULL column without a DEFAULT in a
   single ALTER TABLE statement. The DDL is rejected by SQLite at runtime
   with "Cannot add a NOT NULL column with default value NULL".
2. SQLite does NOT support `ALTER COLUMN ... SET NOT NULL` natively; it
   must be emulated. The combination of `add_column(nullable=True)` +
   backfill + `batch_alter_table(alter_column(nullable=False))` inside
   `op.batch_alter_table` is the established pattern (the 002 migration
   uses the same `batch_alter_table` for its schema change).
3. Re-runnability: the backfill UPDATE has `WHERE uuid IS NULL`, so if
   the migration is interrupted between step 1 and step 2, a second run
   only assigns new uuids to rows that still have NULL. This means the
   migration can be re-applied after a partial failure without producing
   duplicates.

Order of operations (exams -> questions -> answers):
    Step 1. ADD COLUMN uuid VARCHAR(36) NULL
    Step 2. Backfill NULL uuids with Python uuid.uuid4() (parameterized)
    Step 3. ALTER COLUMN uuid SET NOT NULL + CREATE UNIQUE INDEX

The downgrade reverses in reverse FK order (answers -> questions -> exams)
to avoid leaving orphan rows.

Revision ID: 003_add_uuid_columns
Revises: 002_remove_difficulty
Create Date: 2026-06-03 22:00:00.000000
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "003_add_uuid_columns"
down_revision = "002_remove_difficulty"
branch_labels = None
depends_on = None


# Order matters: parents before children on upgrade, children before
# parents on downgrade. exams has no FK into it; questions references
# exams; answers references questions.
UPGRADE_ORDER: tuple[str, ...] = ("exams", "questions", "answers")
DOWNGRADE_ORDER: tuple[str, ...] = ("answers", "questions", "exams")


def _backfill_uuid_column(table: str) -> None:
    """Assign a fresh Python uuid4() to every row whose uuid is still NULL.

    The UPDATE is parameterized (no string interpolation of uuid values
    into SQL) and guarded by `WHERE uuid IS NULL` so the operation is
    re-runnable on a partially-backfilled table.
    """
    conn = op.get_bind()
    select_sql = sa.text(f"SELECT id FROM {table} WHERE uuid IS NULL")
    update_sql = sa.text(
        f"UPDATE {table} SET uuid = :u WHERE id = :i AND uuid IS NULL"
    )
    rows = conn.execute(select_sql).fetchall()
    for (row_id,) in rows:
        conn.execute(update_sql, {"u": str(uuid.uuid4()), "i": row_id})


def upgrade() -> None:
    """Add uuid column to exams, questions, answers; backfill; enforce NOT NULL + unique."""
    for table in UPGRADE_ORDER:
        # Step 1: add nullable column.
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("uuid", sa.String(length=36), nullable=True))

        # Step 2: backfill NULL rows with Python uuid4().
        _backfill_uuid_column(table)

        # Step 3: enforce NOT NULL + create unique index.
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                "uuid",
                existing_type=sa.String(length=36),
                nullable=False,
            )
            batch_op.create_index(f"ix_{table}_uuid", ["uuid"], unique=True)


def downgrade() -> None:
    """Drop uuid column and its unique index from each table in reverse FK order."""
    for table in DOWNGRADE_ORDER:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_index(f"ix_{table}_uuid")
            batch_op.drop_column("uuid")
