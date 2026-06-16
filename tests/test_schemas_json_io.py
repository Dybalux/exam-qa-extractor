"""Tests for the Pydantic schemas in ``app/schemas/json_io.py``.

These tests cover the four guarantees T2.1 makes for the schemas:

1. ``ExportFileSchema`` parses a canonical envelope.
2. ``ConfigDict(strict=True)`` rejects type coercion (e.g. an int
   field rejects a string value).
3. ``ImportPreviewSchema`` and ``ImportApplyResultSchema`` serialize
   round-trip via ``.model_dump(mode="json")``.
4. The "preview" list on :class:`ImportPreviewSchema` defaults to
   ``[]`` (the 50-entry cap is a service-layer policy, not a schema
   constraint — see T2.3).

The plan also notes that ``ExportFileSchema(questions=[])`` is valid
(empty-DB export shape), and that ``MalformedImportError.details`` is
a ``dict`` with a ``validation_errors`` key. Those behaviours are
covered here.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.core.exceptions import (
    MalformedImportError,
    PayloadTooLargeError,
    UnknownSchemaVersion,
)
from app.schemas.json_io import (
    AnswerExportSchema,
    ExamContextExportSchema,
    ExportFileSchema,
    ImportApplyResultSchema,
    ImportPreviewSchema,
    QuestionExportSchema,
)


def _canonical_exam_context() -> dict:
    return {
        "uuid": "11111111-1111-4111-8111-111111111111",
        "partial_number": 1,
        "exam_date": "2024-06-15",
        "topic_tags": "algebra",
    }


def _canonical_answer() -> dict:
    return {
        "uuid": "33333333-3333-4333-8333-333333333333",
        "answer_text": "4",
        "answer_type": "correct",
        "is_common_misconception": False,
        "explanation": None,
        "display_order": 0,
    }


def _canonical_question() -> dict:
    return {
        "uuid": "22222222-2222-4222-8222-222222222222",
        "exam_context": _canonical_exam_context(),
        "question_text": "What is 2+2?",
        "extracted_text": None,
        "topic": "OTHER",
        "order_in_exam": 1,
        "is_corrected": False,
        "correction_notes": None,
        "has_code_in_answers": False,
        "image_id": None,
        "confidence_score": None,
        "answers": [_canonical_answer()],
    }


def _canonical_envelope() -> dict:
    return {
        "schema_version": "1.0",
        "exported_at": "2024-06-15T12:00:00+00:00",
        "questions": [_canonical_question()],
    }


# ---------------------------------------------------------------------------
# Round-trip / shape tests
# ---------------------------------------------------------------------------


def test_export_file_schema_parses_canonical_envelope() -> None:
    """The exact JSON shape a real export emits must parse without errors."""
    envelope = ExportFileSchema.model_validate(_canonical_envelope())
    assert envelope.schema_version == "1.0"
    assert isinstance(envelope.exported_at, datetime)
    assert len(envelope.questions) == 1

    q = envelope.questions[0]
    assert isinstance(q, QuestionExportSchema)
    assert q.uuid == "22222222-2222-4222-8222-222222222222"
    assert isinstance(q.exam_context, ExamContextExportSchema)
    assert q.exam_context.partial_number == 1
    assert isinstance(q.exam_context.exam_date, date)
    assert len(q.answers) == 1
    assert isinstance(q.answers[0], AnswerExportSchema)
    assert q.answers[0].answer_type == "correct"


def test_export_file_schema_accepts_empty_questions_list() -> None:
    """Empty-DB exports have ``questions=[]`` and must still be valid."""
    envelope = ExportFileSchema.model_validate(
        {
            "schema_version": "1.0",
            "exported_at": "2024-06-15T12:00:00+00:00",
            "questions": [],
        }
    )
    assert envelope.questions == []


def test_export_file_schema_strict_rejects_string_partial_number() -> None:
    """Strict mode must reject ``"2"`` (string) for an int field."""
    bad = _canonical_envelope()
    bad["questions"][0]["exam_context"]["partial_number"] = "2"
    with pytest.raises(ValidationError) as exc_info:
        ExportFileSchema.model_validate(bad)
    # Pydantic surfaces the offending field in the error; just assert
    # that the error mentions partial_number.
    assert "partial_number" in str(exc_info.value)


def test_export_file_schema_strict_rejects_string_question_id_like() -> None:
    """Strict mode must reject a string for any int field, e.g. order_in_exam."""
    bad = _canonical_envelope()
    bad["questions"][0]["order_in_exam"] = "1"  # string, not int
    with pytest.raises(ValidationError):
        ExportFileSchema.model_validate(bad)


def test_question_export_schema_requires_min_length_answer_text() -> None:
    """``answer_text`` has ``min_length=1``; an empty string must fail."""
    bad = _canonical_envelope()
    bad["questions"][0]["answers"][0]["answer_text"] = ""
    with pytest.raises(ValidationError):
        ExportFileSchema.model_validate(bad)


def test_question_export_schema_defaults_answers_to_empty_list() -> None:
    """A question with no ``answers`` key must default to an empty list."""
    payload = _canonical_question()
    payload.pop("answers")
    q = QuestionExportSchema.model_validate(payload)
    assert q.answers == []


# ---------------------------------------------------------------------------
# image_id / confidence_score (round-trip preservation)
# ---------------------------------------------------------------------------


def test_question_export_schema_accepts_null_image_id_and_confidence_score() -> None:
    """``image_id`` and ``confidence_score`` are nullable; ``None`` is valid."""
    # The canonical fixture already sets them to ``None``; this is the
    # explicit round-trip check that the field is read back as ``None``.
    envelope = ExportFileSchema.model_validate(_canonical_envelope())
    q = envelope.questions[0]
    assert q.image_id is None
    assert q.confidence_score is None


def test_question_export_schema_strict_rejects_string_confidence_score() -> None:
    """Strict mode rejects a string for the float field ``confidence_score``."""
    payload = _canonical_envelope()
    payload["questions"][0]["confidence_score"] = "0.87"
    with pytest.raises(ValidationError):
        ExportFileSchema.model_validate(payload)


# ---------------------------------------------------------------------------
# Import response shapes
# ---------------------------------------------------------------------------


def test_import_preview_schema_defaults_optional_lists_to_empty() -> None:
    """``validation_errors`` and ``preview`` default to empty lists.

    The integer counts (``to_create``/``to_update``/``to_delete``) are
    required: the service always knows the actual diff size when it
    builds the response, so making them implicit defaults would only
    mask bugs in the diff code.
    """
    preview = ImportPreviewSchema(to_create=0, to_update=0, to_delete=0)
    assert preview.to_create == 0
    assert preview.to_update == 0
    assert preview.to_delete == 0
    assert preview.validation_errors == []
    assert preview.preview == []


def test_import_preview_schema_round_trips_via_model_dump_json() -> None:
    """``ImportPreviewSchema`` must serialize via ``model_dump(mode='json')``."""
    preview = ImportPreviewSchema(
        to_create=5,
        to_update=3,
        to_delete=0,
        validation_errors=[
            {
                "index": 7,
                "uuid": "22222222-2222-4222-8222-222222222222",
                "field_errors": [{"loc": ["topic"], "msg": "invalid value"}],
            }
        ],
        preview=[{"uuid": "abc", "action": "create"}],
    )
    dumped = preview.model_dump(mode="json")
    assert dumped["to_create"] == 5
    assert dumped["to_update"] == 3
    assert dumped["to_delete"] == 0
    assert len(dumped["validation_errors"]) == 1
    assert dumped["validation_errors"][0]["index"] == 7
    assert dumped["validation_errors"][0]["field_errors"][0]["loc"] == ["topic"]
    assert dumped["preview"] == [{"uuid": "abc", "action": "create"}]


def test_import_apply_result_schema_round_trips_via_model_dump_json() -> None:
    """``ImportApplyResultSchema`` must serialize via ``model_dump(mode='json')``."""
    applied_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    result = ImportApplyResultSchema(
        created=5, updated=3, deleted=1, applied_at=applied_at
    )
    dumped = result.model_dump(mode="json")
    assert dumped["created"] == 5
    assert dumped["updated"] == 3
    assert dumped["deleted"] == 1
    # ``applied_at`` must serialize as an ISO-8601 string.
    assert dumped["applied_at"].startswith("2024-06-15T12:00:00")


# ---------------------------------------------------------------------------
# Strict-mode guards on the import response shapes
# ---------------------------------------------------------------------------


def test_import_preview_schema_strict_rejects_string_to_create() -> None:
    """Strict mode on ``ImportPreviewSchema`` rejects string counts."""
    with pytest.raises(ValidationError):
        ImportPreviewSchema.model_validate({"to_create": "5"})


def test_import_apply_result_schema_strict_rejects_string_created() -> None:
    """Strict mode on ``ImportApplyResultSchema`` rejects string counts."""
    with pytest.raises(ValidationError):
        ImportApplyResultSchema.model_validate({"created": "5"})


# ---------------------------------------------------------------------------
# Custom exceptions (T2.1 also adds the three new ones to ``app.core.exceptions``)
# ---------------------------------------------------------------------------


def test_malformed_import_error_carries_validation_errors_in_details() -> None:
    """``MalformedImportError.details["validation_errors"]`` is the contract."""
    errors = [
        {
            "index": 0,
            "uuid": "22222222-2222-4222-8222-222222222222",
            "field_errors": [{"loc": ["topic"], "msg": "invalid value"}],
        }
    ]
    err = MalformedImportError(
        "Import contains malformed entries",
        details={"validation_errors": errors},
    )
    assert err.message == "Import contains malformed entries"
    assert err.details == {"validation_errors": errors}
    assert err.details["validation_errors"] == errors
    # It must be a subclass of the base ``ExamStudyError`` so existing
    # exception handlers (mapped to 500) still work as a fallback.
    from app.core.exceptions import ExamStudyError

    assert isinstance(err, ExamStudyError)


def test_unknown_schema_version_inherits_from_base() -> None:
    """``UnknownSchemaVersion`` must extend ``ExamStudyError``."""
    err = UnknownSchemaVersion("Unknown schema version: 0.9")
    from app.core.exceptions import ExamStudyError

    assert isinstance(err, ExamStudyError)
    assert "0.9" in err.message


def test_payload_too_large_error_inherits_from_base() -> None:
    """``PayloadTooLargeError`` must extend ``ExamStudyError``."""
    err = PayloadTooLargeError("File exceeds 10 MB")
    from app.core.exceptions import ExamStudyError

    assert isinstance(err, ExamStudyError)
    assert "10 MB" in err.message


# ---------------------------------------------------------------------------
# Settings: max_import_size_mb (T2.1 also adds this to ``app.config``)
# ---------------------------------------------------------------------------


def test_settings_max_import_size_mb_default_is_10() -> None:
    """``Settings.max_import_size_mb`` must default to 10."""
    from app.config import Settings

    s = Settings()
    assert s.max_import_size_mb == 10
