"""Service for exporting the full database to JSON and restoring from JSON.

This is the pure service layer for the export/import flow: no HTTP, no
templates, no file I/O. The HTTP layer in PR 3 is a thin wrapper
around this class.

The service is the single source of truth for:

* The export envelope shape (locked at ``schema_version="1.0"``).
* Conflict resolution on import (overwrite by uuid, full restore).
* Atomicity (``apply_import`` runs in one transaction).
* Error reporting on malformed JSON (collect every error, then raise
  ``MalformedImportError`` with a ``validation_errors`` array).

Design contract
---------------

* ``export_full_db()`` returns an :class:`ExportFileSchema` with the
  full DB content. Empty DB → ``questions=[]``.
* ``preview_import(envelope)`` is a pure read; it makes ZERO writes
  to the DB and returns an :class:`ImportPreviewSchema`.
* ``apply_import(envelope)`` runs in exactly ONE
  ``async with self.session.begin():`` transaction. On any error,
  the context manager rolls back automatically.
* All three methods collect every validation error before raising
  (``MalformedImportError`` with a ``validation_errors`` list, per
  decision #113). They never fail-fast on the first error.
* The logger name is the exact string
  ``"app.services.json_io_service"`` (not ``__name__``), per the
  design's structured-logging requirement.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.schemas.json_io import (
    AnswerExportSchema,
    ExamContextExportSchema,
    ExportFileSchema,
    QuestionExportSchema,
)


class JsonIOService:
    """Export/import the full database to/from a JSON envelope."""

    # Locked contract version of the export envelope. Bumping this
    # without a migration strategy is a breaking change for any
    # in-the-wild backup file.
    SUPPORTED_VERSIONS: frozenset[str] = frozenset({"1.0"})

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the service with an async DB session.

        Args:
            session: Async SQLAlchemy session. The service does not
                own the session's lifecycle; the caller is responsible
                for committing or rolling back any unit of work the
                service starts (e.g. the transaction opened by
                ``apply_import``).
        """
        self.session = session
        # The logger name is a fixed string (not ``__name__``) per the
        # design's structured-logging requirement: downstream
        # alerting and log filters key on this exact name.
        self._logger = logging.getLogger("app.services.json_io_service")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    async def export_full_db(self) -> ExportFileSchema:
        """Serialize the full DB to an :class:`ExportFileSchema`.

        Empty DB → ``questions=[]``. The result is callable as
        ``.model_dump(mode="json")`` for the HTTP layer.

        Eager-loading
        -------------
        ``Question.answers`` is loaded with ``selectinload`` to avoid
        the N+1 that a default ``lazy="select"`` relationship would
        cause. ``Question.exam`` is also eagerly loaded so the
        ``exam_context`` denormalization below does not trigger a
        second round-trip per question.
        """
        # Import the model types here (not at module level) so this
        # module does not import the ORM until the service is
        # actually used. Keeps import-time cheap and side-effect free.
        from app.models.answer import Answer
        from app.models.exam import Exam
        from app.models.question import Question

        # Select all questions in one statement, eagerly loading both
        # the answers and the parent exam. ``selectinload`` issues a
        # single follow-up ``IN (...)`` query per relationship
        # instead of one query per parent row.
        stmt = (
            select(Question)
            .options(
                selectinload(Question.answers),
                selectinload(Question.exam),
            )
            .order_by(Question.id.asc())
        )
        result = await self.session.execute(stmt)
        questions = result.scalars().all()

        self._logger.info(
            "exporting full db: %d question(s) with eager-loaded answers+exam",
            len(questions),
        )

        return ExportFileSchema(
            schema_version="1.0",
            exported_at=datetime.now(timezone.utc),
            questions=[self._serialize_question(q) for q in questions],
        )

    # ------------------------------------------------------------------
    # Serialization helpers (export path)
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_answer(answer: "Answer") -> AnswerExportSchema:
        """Convert an :class:`Answer` ORM instance to its export shape."""
        return AnswerExportSchema(
            uuid=answer.uuid,
            answer_text=answer.answer_text,
            answer_type=answer.answer_type,
            is_common_misconception=answer.is_common_misconception,
            explanation=answer.explanation,
            display_order=answer.display_order,
        )

    @staticmethod
    def _serialize_exam_context(exam: "Exam") -> ExamContextExportSchema:
        """Convert an :class:`Exam` to the denormalized exam context."""
        return ExamContextExportSchema(
            uuid=exam.uuid,
            partial_number=exam.partial_number,
            exam_date=exam.exam_date,
            topic_tags=exam.topic_tags,
        )

    def _serialize_question(self, question: "Question") -> QuestionExportSchema:
        """Convert a :class:`Question` to its export shape.

        The exam context is denormalized inline; the answers are
        nested. ``Question.exam`` is guaranteed to be loaded by the
        ``selectinload`` in :meth:`export_full_db`.
        """
        return QuestionExportSchema(
            uuid=question.uuid,
            exam_context=self._serialize_exam_context(question.exam),
            question_text=question.question_text,
            extracted_text=question.extracted_text,
            topic=question.topic,
            order_in_exam=question.order_in_exam,
            is_corrected=question.is_corrected,
            correction_notes=question.correction_notes,
            has_code_in_answers=question.has_code_in_answers,
            answers=[
                self._serialize_answer(a) for a in sorted(question.answers, key=lambda a: a.display_order)
            ],
        )
