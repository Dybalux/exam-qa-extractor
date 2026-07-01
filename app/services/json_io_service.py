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
* ``preview_import(json_data)`` is a pure read; it makes ZERO writes
  to the DB and returns an :class:`ImportPreviewSchema`. The argument
  is the raw JSON-loaded ``dict`` (or an already-validated
  :class:`ExportFileSchema` instance). The service handles schema-
  version validation and per-entry Pydantic validation, collecting
  every error before raising.
* ``apply_import(json_data)`` runs in exactly ONE
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
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

if TYPE_CHECKING:
    from app.models.answer import Answer
    from app.models.exam import Exam
    from app.models.question import Question
    from app.models.topic import Topic

from app.core.exceptions import MalformedImportError, UnknownSchemaVersion
from app.schemas.json_io import (
    AnswerExportSchema,
    ExamContextExportSchema,
    ExportFileSchema,
    ImportApplyResultSchema,
    ImportPreviewSchema,
    QuestionExportSchema,
)

# Cap on the number of preview entries returned by ``preview_import``.
# The cap is a service-layer policy; the schema allows any number
# (see ``ImportPreviewSchema.preview``). Keeping the cap in code
# means we can change it without a schema migration.
PREVIEW_ENTRY_CAP = 50


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

        ``image_id`` and ``confidence_score`` are included so the
        round-trip preserves them. See
        :class:`~app.schemas.json_io.QuestionExportSchema` for why
        ``image_id`` is NOT severed on import.
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
            image_id=question.image_id,
            confidence_score=question.confidence_score,
            answers=[
                self._serialize_answer(a)
                for a in sorted(question.answers, key=lambda a: a.display_order)
            ],
        )

    # ------------------------------------------------------------------
    # Import: parse helpers
    # ------------------------------------------------------------------

    def _check_schema_version(self, json_data: dict) -> None:
        """Validate ``schema_version`` is in :attr:`SUPPORTED_VERSIONS`.

        Raises :class:`UnknownSchemaVersion` with the offending
        version and the supported set in the message. Must run
        BEFORE any per-entry validation so the user gets a clear
        "this file is from a different schema version" error rather
        than a confusing per-field Pydantic error.
        """
        version = json_data.get("schema_version")
        if version not in self.SUPPORTED_VERSIONS:
            raise UnknownSchemaVersion(
                f"Unknown schema_version: {version!r}. "
                f"Supported versions: {sorted(self.SUPPORTED_VERSIONS)}"
            )

    def _parse_questions(self, raw_questions: list[Any]) -> list[QuestionExportSchema]:
        """Validate each question entry, collecting every error.

        Per decision #113, this method does NOT fail-fast. It tries
        ``QuestionExportSchema.model_validate`` on every entry; on
        failure it appends a ``{index, uuid, field_errors}`` record
        to ``errors`` and continues. If any errors were collected,
        it raises :class:`MalformedImportError` with a single
        ``validation_errors`` list describing every failure. This
        lets the user fix all problems in one round-trip.

        The function returns a list of parsed
        :class:`QuestionExportSchema` only when no entry failed;
        on failure, the returned list is not used (the exception
        short-circuits the caller).
        """
        errors: list[dict] = []
        parsed: list[QuestionExportSchema] = []
        for idx, raw in enumerate(raw_questions):
            try:
                parsed.append(QuestionExportSchema.model_validate(raw))
            except ValidationError as ve:
                # Best-effort extract of the entry's uuid for the error
                # record. ``raw`` may be any type (Pydantic accepts
                # dicts; we want to stay defensive).
                entry_uuid: str | None = None
                if isinstance(raw, dict):
                    raw_uuid = raw.get("uuid")
                    if isinstance(raw_uuid, str):
                        entry_uuid = raw_uuid
                errors.append(
                    {
                        "index": idx,
                        "uuid": entry_uuid,
                        "field_errors": [
                            {
                                "loc": list(err.get("loc", ())),
                                "msg": err.get("msg", ""),
                                "type": err.get("type", ""),
                            }
                            for err in ve.errors()
                        ],
                    }
                )

        if errors:
            self._logger.warning(
                "preview rejected: %d malformed question entry/entries",
                len(errors),
            )
            raise MalformedImportError(
                "Import contains malformed entries",
                details={"validation_errors": errors},
            )
        return parsed

    def _parse_envelope(
        self, json_data: dict | ExportFileSchema
    ) -> tuple[ExportFileSchema, list[QuestionExportSchema]]:
        """Parse and validate a raw ``dict`` (or pass through an envelope).

        Returns a tuple of the fully-parsed :class:`ExportFileSchema`
        and the per-entry :class:`QuestionExportSchema` list. The
        tuple is the result of running both ``_check_schema_version``
        and ``_parse_questions``; either step raising aborts both.
        """
        if isinstance(json_data, ExportFileSchema):
            # Already-validated envelope: re-run the per-entry parse
            # to be defensive (a caller may have constructed the
            # envelope with default values for everything else).
            return json_data, self._parse_questions(
                [q.model_dump() for q in json_data.questions]
            )
        if not isinstance(json_data, dict):
            raise MalformedImportError(
                "Import payload must be a JSON object",
                details={"received_type": type(json_data).__name__},
            )
        self._check_schema_version(json_data)
        # ``questions`` is optional in the envelope; default to [].
        raw_questions = json_data.get("questions", []) or []
        parsed_questions = self._parse_questions(raw_questions)
        envelope = ExportFileSchema.model_validate(json_data)
        return envelope, parsed_questions

    # ------------------------------------------------------------------
    # Import: diff helpers
    # ------------------------------------------------------------------

    async def _load_topics_map(self) -> dict[str, Topic]:
        """Load all Topic records into a slug→Topic dict.

        Bulk select avoids N+1 queries when resolving topic slugs
        during import (design decision: bulk select over per-record fetch).
        """
        from app.models.topic import Topic

        result = await self.session.execute(select(Topic))
        return {t.slug: t for t in result.scalars().all()}

    async def _resolve_or_create_topic(
        self,
        topic_slug: str,
        topics_map: dict[str, "Topic"],
        *,
        _default_subject_slug: str = "sistemas-operativos",
    ) -> "Topic":
        """Resolve a topic slug to a Topic, creating it if missing.

        Per REQ-IMP-2: unrecognized topics are dynamically created
        under the default Subject (slugged 'sistemas-operativos').

        Args:
            topic_slug: The topic slug from the import payload.
            topics_map: Existing topics dict (mutated in-place on create).
            _default_subject_slug: Slug of the fallback parent Subject.

        Returns:
            The existing or newly-created Topic instance.
        """
        from app.models.subject import Subject
        from app.models.topic import Topic

        if topic_slug in topics_map:
            return topics_map[topic_slug]

        # Resolve default subject.
        subj_result = await self.session.execute(
            select(Subject).where(Subject.slug == _default_subject_slug)
        )
        subject = subj_result.scalar_one_or_none()

        # If default subject is missing, create it.
        if subject is None:
            subject = Subject(name="Sistemas Operativos", slug=_default_subject_slug)
            self.session.add(subject)
            await self.session.flush()

        topic = Topic(name=topic_slug, slug=topic_slug, subject_id=subject.id)
        self.session.add(topic)
        await self.session.flush()
        topics_map[topic_slug] = topic
        self._logger.info("dynamically created topic: %s", topic_slug)
        return topic

    async def _load_questions_with_relations(
        self,
    ) -> list["Question"]:
        """Load every question with its answers and parent exam eagerly.

        Used by both ``preview_import`` and ``apply_import`` to read
        the DB state in O(1) queries. ``selectinload`` issues a
        single ``IN (...)`` follow-up per relationship, avoiding the
        N+1 that default lazy loading would cause.
        """
        from app.models.question import Question

        stmt = select(Question).options(
            selectinload(Question.answers),
            selectinload(Question.exam),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _question_matches_db(
        json_q: QuestionExportSchema,
        db_q: "Question",
        db_exam: "Exam",
    ) -> bool:
        """Return True iff the JSON question matches the DB row at the field level.

        Only fields present in the export shape are compared; the
        DB-only fields (``created_at``, ``updated_at``) are not in
        scope. A question whose DB row matches the JSON on every
        export field is reported as ``to_update=0`` (no change).

        ``image_id`` and ``confidence_score`` ARE in scope (they are
        part of the export shape). Without including them, the diff
        would silently miss edits to these fields, and the apply
        path would emit a no-op when a real change was pending.
        """
        # Scalar question fields
        if db_q.question_text != json_q.question_text:
            return False
        if db_q.extracted_text != json_q.extracted_text:
            return False
        if db_q.topic != json_q.topic:
            return False
        if db_q.order_in_exam != json_q.order_in_exam:
            return False
        if db_q.is_corrected != json_q.is_corrected:
            return False
        if db_q.correction_notes != json_q.correction_notes:
            return False
        if db_q.has_code_in_answers != json_q.has_code_in_answers:
            return False
        if db_q.image_id != json_q.image_id:
            return False
        if db_q.confidence_score != json_q.confidence_score:
            return False

        # Denormalized exam context
        if db_exam.partial_number != json_q.exam_context.partial_number:
            return False
        if db_exam.exam_date != json_q.exam_context.exam_date:
            return False
        if db_exam.topic_tags != json_q.exam_context.topic_tags:
            return False

        # Answers: same uuids AND same field values
        db_answers_by_uuid = {a.uuid: a for a in db_q.answers}
        json_answers_by_uuid = {a.uuid: a for a in json_q.answers}
        if db_answers_by_uuid.keys() != json_answers_by_uuid.keys():
            return False
        for ans_uuid, json_a in json_answers_by_uuid.items():
            db_a = db_answers_by_uuid[ans_uuid]
            if db_a.answer_text != json_a.answer_text:
                return False
            if db_a.answer_type != json_a.answer_type:
                return False
            if db_a.is_common_misconception != json_a.is_common_misconception:
                return False
            if db_a.explanation != json_a.explanation:
                return False
            if db_a.display_order != json_a.display_order:
                return False

        return True

    # ------------------------------------------------------------------
    # Import: preview (dry-run)
    # ------------------------------------------------------------------

    async def preview_import(
        self, json_data: dict | ExportFileSchema
    ) -> ImportPreviewSchema:
        """Dry-run an import: diff JSON vs DB, never write.

        Returns an :class:`ImportPreviewSchema` with the diff counts
        and a sample of the changes (capped at ``PREVIEW_ENTRY_CAP``
        entries). The DB is NOT modified; no ``session.add`` or
        ``delete`` is called.

        Raises
        ------
        UnknownSchemaVersion
            If ``schema_version`` is not in ``SUPPORTED_VERSIONS``.
        MalformedImportError
            If any question entry fails Pydantic validation. The
            error's ``details["validation_errors"]`` contains every
            failure (``{index, uuid, field_errors: [...]}``) so the
            user can fix them all in one round-trip.
        """
        # Lazy import keeps this module free of ORM imports until
        # the service is actually used.

        _, parsed_questions = self._parse_envelope(json_data)

        # Read DB state in O(1) queries (selectinload on answers + exam).
        db_questions = await self._load_questions_with_relations()
        db_by_uuid: dict[str, tuple[Question, Exam]] = {
            q.uuid: (q, q.exam) for q in db_questions
        }
        json_uuids = {q.uuid for q in parsed_questions}

        to_create = 0
        to_update = 0
        to_delete = 0
        preview: list[dict] = []

        for json_q in parsed_questions:
            matched = db_by_uuid.get(json_q.uuid)
            if matched is None:
                # New row the JSON introduces
                to_create += 1
                if len(preview) < PREVIEW_ENTRY_CAP:
                    preview.append({"action": "create", "uuid": json_q.uuid})
            else:
                db_q, db_exam = matched
                if not self._question_matches_db(json_q, db_q, db_exam):
                    to_update += 1
                    if len(preview) < PREVIEW_ENTRY_CAP:
                        preview.append({"action": "update", "uuid": json_q.uuid})
                # else: identical → no counter incremented

        # Orphans: uuids in the DB that the JSON does not carry.
        for db_uuid in db_by_uuid:
            if db_uuid not in json_uuids:
                to_delete += 1
                if len(preview) < PREVIEW_ENTRY_CAP:
                    preview.append({"action": "delete", "uuid": db_uuid})

        self._logger.info(
            "preview to_create=%d to_update=%d to_delete=%d",
            to_create,
            to_update,
            to_delete,
        )

        return ImportPreviewSchema(
            to_create=to_create,
            to_update=to_update,
            to_delete=to_delete,
            validation_errors=[],
            preview=preview,
        )

    # ------------------------------------------------------------------
    # Import: apply (atomic, destructive, full restore)
    # ------------------------------------------------------------------

    @staticmethod
    def _answer_matches_db(json_a: AnswerExportSchema, db_a: "Answer") -> bool:
        """Return True iff the JSON answer matches the DB row's fields.

        Only fields present in :class:`AnswerExportSchema` are
        compared. A match means the apply path treats the row as
        unchanged (no UPDATE issued, ``updated`` counter not
        incremented). This is what makes the second apply of an
        identical envelope return ``updated=0`` (idempotency).
        """
        return (
            db_a.answer_text == json_a.answer_text
            and db_a.answer_type == json_a.answer_type
            and db_a.is_common_misconception == json_a.is_common_misconception
            and db_a.explanation == json_a.explanation
            and db_a.display_order == json_a.display_order
        )

    async def apply_import(
        self, json_data: dict | ExportFileSchema
    ) -> ImportApplyResultSchema:
        """Apply an import envelope: full restore, atomic, destructive.

        The DB ends up exactly equal to the JSON's intent: rows
        whose uuid is in the JSON are upserted (overwrite-by-uuid,
        JSON wins); rows whose uuid is NOT in the JSON are deleted
        (full-restore, including orphan children).

        The whole operation runs in exactly ONE
        ``async with self.session.begin():`` transaction. On any
        exception (Pydantic error, DB ``IntegrityError``, anything),
        the context manager rolls back automatically — the DB is
        left in its pre-import state.

        Idempotency
        -----------

        Because the apply path uses per-field comparison (the same
        helper :meth:`_question_matches_db` the preview path uses),
        a second apply of an envelope that already matches the DB
        returns ``created=0, updated=0, deleted=0`` — a true
        no-op. The plan requires this; the design's example did
        not, so the implementation follows the plan.

        Order inside the transaction
        ----------------------------

        1. Parse ALL questions, collect every error, raise
           :class:`MalformedImportError` if any (no writes yet).
        2. Compute orphan set-diffs (answers → questions → exams).
        3. DELETE orphan answers, then orphan questions, then
           orphan exams (children before parents — explicit even
           though cascade handles it; the plan calls for the
           explicit ordering).
        4. UPSERT exams by uuid.
        5. ``session.flush()`` (assigns ids to new exams).
        6. UPSERT questions by uuid.
        7. ``session.flush()`` (assigns ids to new questions).
        8. UPSERT answers by uuid.

        NO ``session.merge()`` (per design decision): the upsert
        is explicit ``SELECT by uuid; if exists: update; else:
        insert`` so the per-row "created vs updated" count is
        unambiguous.

        Raises
        ------
        UnknownSchemaVersion
            If ``schema_version`` is not in ``SUPPORTED_VERSIONS``.
        MalformedImportError
            If any question entry fails Pydantic validation. The
            transaction is NOT opened (validation runs first).
        sqlalchemy.exc.IntegrityError
            (or any other DB error) mid-transaction. The context
            manager rolls back; the DB is unchanged.
        """
        # Lazy imports keep this module free of ORM imports at
        # module load time.
        from app.models.answer import Answer
        from app.models.exam import Exam
        from app.models.question import Question

        # Step 1: parse + collect errors. No writes yet.
        _, parsed_questions = self._parse_envelope(json_data)

        json_exam_uuids: set[str] = {q.exam_context.uuid for q in parsed_questions}
        json_question_uuids: set[str] = {q.uuid for q in parsed_questions}
        json_answer_uuids: set[str] = {
            a.uuid for q in parsed_questions for a in q.answers
        }

        async with self.session.begin():
            # Step 2: read DB state in O(1) queries.
            db_questions = await self._load_questions_with_relations()
            db_question_by_uuid: dict[str, Question] = {q.uuid: q for q in db_questions}
            db_exam_by_uuid: dict[str, Exam] = {
                q.exam.uuid: q.exam for q in db_questions
            }
            db_answers_result = await self.session.execute(select(Answer))
            db_answers = list(db_answers_result.scalars().all())
            db_answer_by_uuid: dict[str, Answer] = {a.uuid: a for a in db_answers}

            # Pre-fetch all topics into a slug→Topic map (bulk select, O(1)).
            topics_map = await self._load_topics_map()

            created = 0
            updated = 0
            deleted = 0

            # Step 3: DELETE orphans (children first).
            for ans_uuid in list(db_answer_by_uuid.keys()):
                if ans_uuid not in json_answer_uuids:
                    await self.session.delete(db_answer_by_uuid[ans_uuid])
                    deleted += 1
            for q_uuid in list(db_question_by_uuid.keys()):
                if q_uuid not in json_question_uuids:
                    await self.session.delete(db_question_by_uuid[q_uuid])
                    deleted += 1
            for e_uuid in list(db_exam_by_uuid.keys()):
                if e_uuid not in json_exam_uuids:
                    await self.session.delete(db_exam_by_uuid[e_uuid])
                    deleted += 1

            # Step 4: UPSERT exams by uuid. ``exam_map`` starts from
            # the surviving (non-orphan) DB rows; we add newly
            # created Exam instances as we encounter them.
            exam_map: dict[str, Exam] = {
                uuid: e
                for uuid, e in db_exam_by_uuid.items()
                if uuid in json_exam_uuids
            }
            for json_q in parsed_questions:
                ec = json_q.exam_context
                existing = exam_map.get(ec.uuid)
                if existing is not None:
                    if (
                        existing.partial_number != ec.partial_number
                        or existing.exam_date != ec.exam_date
                        or existing.topic_tags != ec.topic_tags
                    ):
                        existing.partial_number = ec.partial_number
                        existing.exam_date = ec.exam_date
                        existing.topic_tags = ec.topic_tags
                        updated += 1
                else:
                    new_exam = Exam(
                        uuid=ec.uuid,
                        partial_number=ec.partial_number,
                        exam_date=ec.exam_date,
                        topic_tags=ec.topic_tags,
                    )
                    self.session.add(new_exam)
                    exam_map[ec.uuid] = new_exam
                    created += 1

            # Step 5: flush so newly-created exams get their ids.
            await self.session.flush()

            # Step 6: UPSERT questions by uuid. ``question_map`` is
            # seeded from surviving DB rows.
            question_map: dict[str, Question] = {
                uuid: q
                for uuid, q in db_question_by_uuid.items()
                if uuid in json_question_uuids
            }
            for json_q in parsed_questions:
                exam = exam_map[json_q.exam_context.uuid]
                topic_obj = await self._resolve_or_create_topic(
                    json_q.topic, topics_map
                )
                existing = question_map.get(json_q.uuid)
                if existing is not None:
                    if not self._question_matches_db(json_q, existing, existing.exam):
                        existing.question_text = json_q.question_text
                        existing.extracted_text = json_q.extracted_text
                        existing.topic_id = topic_obj.id
                        existing.order_in_exam = json_q.order_in_exam
                        existing.is_corrected = json_q.is_corrected
                        existing.correction_notes = json_q.correction_notes
                        existing.has_code_in_answers = json_q.has_code_in_answers
                        existing.image_id = json_q.image_id
                        existing.confidence_score = json_q.confidence_score
                        updated += 1
                else:
                    new_q = Question(
                        uuid=json_q.uuid,
                        exam_id=exam.id,
                        question_text=json_q.question_text,
                        extracted_text=json_q.extracted_text,
                        topic_id=topic_obj.id,
                        order_in_exam=json_q.order_in_exam,
                        is_corrected=json_q.is_corrected,
                        correction_notes=json_q.correction_notes,
                        has_code_in_answers=json_q.has_code_in_answers,
                        image_id=json_q.image_id,
                        confidence_score=json_q.confidence_score,
                    )
                    self.session.add(new_q)
                    question_map[json_q.uuid] = new_q
                    created += 1

            # Step 7: flush so newly-created questions get their ids.
            await self.session.flush()

            # Step 8: UPSERT answers by uuid. The parent's id is
            # taken from ``question_map`` (which now has ids for
            # both surviving and newly-created questions).
            for json_q in parsed_questions:
                parent_q = question_map[json_q.uuid]
                for json_a in json_q.answers:
                    existing = db_answer_by_uuid.get(json_a.uuid)
                    if existing is not None:
                        if not self._answer_matches_db(json_a, existing):
                            existing.answer_text = json_a.answer_text
                            existing.answer_type = json_a.answer_type
                            existing.is_common_misconception = (
                                json_a.is_common_misconception
                            )
                            existing.explanation = json_a.explanation
                            existing.display_order = json_a.display_order
                            updated += 1
                    else:
                        new_a = Answer(
                            uuid=json_a.uuid,
                            question_id=parent_q.id,
                            answer_text=json_a.answer_text,
                            answer_type=json_a.answer_type,
                            is_common_misconception=(json_a.is_common_misconception),
                            explanation=json_a.explanation,
                            display_order=json_a.display_order,
                        )
                        self.session.add(new_a)
                        created += 1

        self._logger.info(
            "apply_import committed created=%d updated=%d deleted=%d",
            created,
            updated,
            deleted,
        )

        return ImportApplyResultSchema(
            created=created,
            updated=updated,
            deleted=deleted,
            applied_at=datetime.now(timezone.utc),
        )
