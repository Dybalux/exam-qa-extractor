"""Add error_review mode to practice_sessions CHECK constraint.

Expands the ``check_valid_practice_mode`` constraint on
``practice_sessions.mode`` to accept ``'error_review'`` as a
valid mode value. The constraint is dropped and recreated via
``batch_alter_table`` with ``recreate='always'`` (required for
SQLite constraint modifications).

The downgrade path restores the previous constraint without
``'error_review'``. Any ``error_review`` sessions (and their
responses) are deleted before recreating the constraint so the
table rebuild does not violate it mid-rebuild.

Revision ID: 006_add_error_review_mode
Revises: 005_drop_topic_column
Create Date: 2026-07-03 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "006_add_error_review_mode"
down_revision = "005_drop_topic_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop and recreate check_valid_practice_mode including 'error_review'."""
    with op.batch_alter_table("practice_sessions", recreate="always") as batch_op:
        batch_op.drop_constraint("check_valid_practice_mode", type_="check")
        batch_op.create_check_constraint(
            "check_valid_practice_mode",
            "mode IN ('random', 'by_partial', 'by_topic', 'exam_simulation', 'error_review')",
        )


def downgrade() -> None:
    """Restore check_valid_practice_mode excluding 'error_review'.

    ``batch_alter_table(recreate='always')`` rebuilds the table via
    ``INSERT INTO new SELECT FROM old``. If any row has
    ``mode='error_review'`` the INSERT would violate the recreated
    constraint mid-rebuild, leaving the DB in a broken state. We
    therefore delete error_review sessions (and their cascading
    responses) before recreating the constraint so the downgrade is
    safe and reversible.
    """
    # Clean up error_review rows first — responses reference sessions
    # via FK, so delete them before their parent sessions.
    op.execute(
        "DELETE FROM practice_responses WHERE session_id IN "
        "(SELECT id FROM practice_sessions WHERE mode = 'error_review')"
    )
    op.execute("DELETE FROM practice_sessions WHERE mode = 'error_review'")

    with op.batch_alter_table("practice_sessions", recreate="always") as batch_op:
        batch_op.drop_constraint("check_valid_practice_mode", type_="check")
        batch_op.create_check_constraint(
            "check_valid_practice_mode",
            "mode IN ('random', 'by_partial', 'by_topic', 'exam_simulation')",
        )
