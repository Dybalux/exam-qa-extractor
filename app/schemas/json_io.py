"""Pydantic schemas for the JSON export/import flow.

These schemas are the contract between the database layer and the JSON
file format used by ``POST /api/v1/export`` and ``POST /api/v1/import``.

Design notes
------------

* All schemas use ``ConfigDict(strict=True)`` so Pydantic does NOT
  coerce primitive types (e.g. an ``int`` field rejects the string
  ``"2"``). This catches subtle malformed entries early and aligns
  with decision #113 ("REJECT ALL on Pydantic validation failure").

* ``date`` and ``datetime`` fields are declared with
  ``Field(strict=False)`` so the schema can still parse the JSON
  envelope, where dates are ISO-8601 strings. The per-field override
  is needed because strict mode in Pydantic v2 rejects string
  coercion for *every* type, including date/datetime — which would
  break JSON parsing. By keeping primitive fields (``int``/``bool``)
  strict and relaxing only the temporal fields, we get the "strict
  primitive types, lax ISO-8601 dates" combination the export
  envelope requires.

* The export shape is a single flat-questions envelope. Exam context
  is denormalized into each question via
  ``exam_context: ExamContextExportSchema``; answers are nested
  under each question. There is no top-level ``exams`` array.

* The "preview" list on :class:`ImportPreviewSchema` defaults to an
  empty list. The 50-entry cap is a service-layer policy; the schema
  itself does not enforce it.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# Type aliases for fields that must accept ISO-8601 strings from the
# JSON envelope while the rest of the model stays strict. Without this
# per-field override, ``ConfigDict(strict=True)`` would reject
# string-to-date coercion and the envelope could not be parsed.
DateField = Annotated[date, Field(strict=False)]
DatetimeField = Annotated[datetime, Field(strict=False)]


# ---------------------------------------------------------------------------
# Export envelope
# ---------------------------------------------------------------------------


class ExamContextExportSchema(BaseModel):
    """Denormalized exam context attached to each exported question.

    Carries just enough information to recreate the parent ``Exam``
    row on import: its stable ``uuid`` plus the user-editable fields
    (``partial_number``, ``exam_date``, ``topic_tags``).
    """

    model_config = ConfigDict(strict=True)

    uuid: str
    partial_number: int = Field(..., ge=1, le=4)
    exam_date: DateField | None
    topic_tags: str | None


class AnswerExportSchema(BaseModel):
    """One answer belonging to a :class:`QuestionExportSchema`."""

    model_config = ConfigDict(strict=True)

    uuid: str
    answer_text: str = Field(..., min_length=1)
    answer_type: str
    is_common_misconception: bool
    explanation: str | None
    display_order: int


class QuestionExportSchema(BaseModel):
    """One question entry in the export envelope.

    The parent exam is denormalized into ``exam_context``; the answers
    are nested inline. This keeps the envelope a single flat array
    of questions and matches the spec's locked shape.
    """

    model_config = ConfigDict(strict=True)

    uuid: str
    exam_context: ExamContextExportSchema
    question_text: str = Field(..., min_length=1)
    extracted_text: str | None
    topic: str
    order_in_exam: int | None
    is_corrected: bool
    correction_notes: str | None
    has_code_in_answers: bool
    answers: list[AnswerExportSchema] = Field(default_factory=list)


class ExportFileSchema(BaseModel):
    """Top-level envelope written to disk on export.

    ``schema_version`` is the contract version of the JSON shape. The
    service refuses to import an envelope whose version is not in
    ``JsonIOService.SUPPORTED_VERSIONS`` and raises
    :class:`~app.core.exceptions.UnknownSchemaVersion`.

    ``exported_at`` is an aware UTC timestamp at the moment the
    export was generated.
    """

    model_config = ConfigDict(strict=True)

    schema_version: str
    exported_at: DatetimeField
    questions: list[QuestionExportSchema] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Import response shapes
# ---------------------------------------------------------------------------


class ImportPreviewSchema(BaseModel):
    """Dry-run result returned by :meth:`JsonIOService.preview_import`.

    ``to_create`` / ``to_update`` / ``to_delete`` are integer counts
    matching the action the apply path would take. ``validation_errors``
    is a list of ``{index, uuid, field_errors: [...]}`` entries
    describing every entry that failed Pydantic validation; per
    decision #113, the apply path refuses to run if this list is
    non-empty, so the dry-run and the apply path share the same
    "reject all on malformed" semantics.

    ``preview`` is a sample of the changes (capped at 50 entries by
    the service). It is opaque from the schema's perspective: the
    service decides what shape each entry takes.
    """

    model_config = ConfigDict(strict=True)

    to_create: int
    to_update: int
    to_delete: int
    validation_errors: list[dict] = Field(default_factory=list)
    preview: list[dict] = Field(default_factory=list)


class ImportApplyResultSchema(BaseModel):
    """Result returned by :meth:`JsonIOService.apply_import`.

    Because the apply path collects every validation error and raises
    before opening a transaction, a successful apply never has a
    ``skipped`` counter — either everything was applied, or nothing
    was. The ``applied_at`` is an aware UTC timestamp set right
    before the transaction commits.
    """

    model_config = ConfigDict(strict=True)

    created: int
    updated: int
    deleted: int
    applied_at: DatetimeField
