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
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.drop_constraint('check_valid_difficulty', type_='check')
        batch_op.drop_column('difficulty')


def downgrade() -> None:
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('difficulty', sa.Integer(), nullable=False, server_default='3'),
        )
        batch_op.create_check_constraint(
            'check_valid_difficulty',
            'difficulty BETWEEN 1 AND 5',
        )
