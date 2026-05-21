"""Remove difficulty column from questions table.

Revision ID: 002_remove_difficulty
Revises: 001_initial
Create Date: 2026-05-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_remove_difficulty'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('check_valid_difficulty', 'questions', type_='check')
    op.drop_column('questions', 'difficulty')


def downgrade() -> None:
    op.add_column(
        'questions',
        sa.Column('difficulty', sa.Integer(), nullable=False, server_default='3'),
    )
    op.create_check_constraint(
        'check_valid_difficulty',
        'questions',
        'difficulty BETWEEN 1 AND 5',
    )
