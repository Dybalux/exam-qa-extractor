"""Initial migration with all models.

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create exams table
    op.create_table(
        "exams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("partial_number", sa.Integer(), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=True),
        sa.Column("topic_tags", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exams")),
        sa.CheckConstraint(
            "partial_number IN (1, 2, 3, 4)", name="check_valid_partial_number"
        ),
    )
    op.create_index("idx_exam_date", "exams", ["exam_date"])
    op.create_index("idx_exam_partial", "exams", ["partial_number"])

    # Create exam_images table
    op.create_table(
        "exam_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exam_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("original_path", sa.String(length=500), nullable=False),
        sa.Column("ocr_status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["exam_id"],
            ["exams.id"],
            ondelete="CASCADE",
            name=op.f("fk_exam_images_exam_id_exams"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exam_images")),
    )
    op.create_index("idx_exam_image_exam", "exam_images", ["exam_id"])
    op.create_index("idx_exam_image_status", "exam_images", ["ocr_status"])

    # Create questions table
    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exam_id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("topic", sa.String(length=50), nullable=False),
        sa.Column("order_in_exam", sa.Integer(), nullable=True),
        sa.Column("is_corrected", sa.Boolean(), nullable=False),
        sa.Column("correction_notes", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("has_code_in_answers", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["exam_id"],
            ["exams.id"],
            ondelete="CASCADE",
            name=op.f("fk_questions_exam_id_exams"),
        ),
        sa.ForeignKeyConstraint(
            ["image_id"],
            ["exam_images.id"],
            ondelete="SET NULL",
            name=op.f("fk_questions_image_id_exam_images"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questions")),
        sa.CheckConstraint("difficulty BETWEEN 1 AND 5", name="check_valid_difficulty"),
        sa.CheckConstraint("order_in_exam BETWEEN 1 AND 50", name="check_valid_order"),
    )
    op.create_index("idx_question_corrected", "questions", ["is_corrected"])
    op.create_index("idx_question_exam", "questions", ["exam_id"])
    op.create_index("idx_question_topic", "questions", ["topic"])

    # Create answers table
    op.create_table(
        "answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("answer_type", sa.String(length=20), nullable=False),
        sa.Column("is_common_misconception", sa.Boolean(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            ondelete="CASCADE",
            name=op.f("fk_answers_question_id_questions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_answers")),
        sa.CheckConstraint(
            "answer_type IN ('correct', 'incorrect', 'partial')",
            name="check_valid_answer_type",
        ),
    )
    op.create_index("idx_answer_question", "answers", ["question_id"])
    op.create_index("idx_answer_type", "answers", ["answer_type"])

    # Create practice_sessions table
    op.create_table(
        "practice_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_session_id", sa.String(length=100), nullable=False),
        sa.Column("mode", sa.String(length=30), nullable=False),
        sa.Column("exam_id", sa.Integer(), nullable=True),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("questions_answered", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("incorrect_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_time_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["exam_id"],
            ["exams.id"],
            ondelete="SET NULL",
            name=op.f("fk_practice_sessions_exam_id_exams"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_practice_sessions")),
        sa.CheckConstraint(
            "mode IN ('random', 'by_partial', 'by_topic', 'exam_simulation')",
            name="check_valid_practice_mode",
        ),
    )
    op.create_index("idx_session_exam", "practice_sessions", ["exam_id"])
    op.create_index("idx_session_user", "practice_sessions", ["user_session_id"])

    # Create practice_responses table
    op.create_table(
        "practice_responses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("selected_answer_id", sa.Integer(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=False),
        sa.Column("was_flagged", sa.Boolean(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retry_of", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            ondelete="CASCADE",
            name=op.f("fk_practice_responses_question_id_questions"),
        ),
        sa.ForeignKeyConstraint(
            ["retry_of"],
            ["practice_responses.id"],
            ondelete="SET NULL",
            name=op.f("fk_practice_responses_retry_of_practice_responses"),
        ),
        sa.ForeignKeyConstraint(
            ["selected_answer_id"],
            ["answers.id"],
            ondelete="SET NULL",
            name=op.f("fk_practice_responses_selected_answer_id_answers"),
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["practice_sessions.id"],
            ondelete="CASCADE",
            name=op.f("fk_practice_responses_session_id_practice_sessions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_practice_responses")),
    )
    op.create_index("idx_response_question", "practice_responses", ["question_id"])
    op.create_index("idx_response_session", "practice_responses", ["session_id"])


def downgrade() -> None:
    op.drop_table("practice_responses")
    op.drop_table("practice_sessions")
    op.drop_table("answers")
    op.drop_table("questions")
    op.drop_table("exam_images")
    op.drop_table("exams")
