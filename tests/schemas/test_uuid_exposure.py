"""Tests for uuid exposure in Pydantic response schemas."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.schemas.answer import AnswerResponse
from app.schemas.exam import ExamResponse
from app.schemas.question import QuestionResponse


def _exam_obj(uuid: str = "exam-uuid-1") -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        uuid=uuid,
        partial_number=1,
        exam_date=date(2026, 6, 3),
        topic_tags="algebra",
        created_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
    )


def _question_obj(uuid: str = "question-uuid-1") -> SimpleNamespace:
    return SimpleNamespace(
        id=10,
        uuid=uuid,
        exam_id=1,
        image_id=None,
        question_text="What is 2+2?",
        extracted_text=None,
        confidence_score=None,
        topic="OTHER",
        order_in_exam=1,
        is_corrected=False,
        correction_notes=None,
        has_code_in_answers=False,
        is_ready_for_practice=True,
        created_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
    )


def _answer_obj(uuid: str = "answer-uuid-1") -> SimpleNamespace:
    return SimpleNamespace(
        id=100,
        uuid=uuid,
        question_id=10,
        answer_text="4",
        answer_type="correct",
        is_correct=True,
        is_common_misconception=False,
        explanation=None,
        display_order=0,
        created_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
    )


def test_exam_response_includes_uuid() -> None:
    response = ExamResponse.model_validate(_exam_obj())
    dumped = response.model_dump()
    assert "uuid" in dumped
    assert dumped["uuid"] == "exam-uuid-1"


def test_question_response_includes_uuid() -> None:
    response = QuestionResponse.model_validate(_question_obj())
    dumped = response.model_dump()
    assert "uuid" in dumped
    assert dumped["uuid"] == "question-uuid-1"


def test_answer_response_includes_uuid() -> None:
    response = AnswerResponse.model_validate(_answer_obj())
    dumped = response.model_dump()
    assert "uuid" in dumped
    assert dumped["uuid"] == "answer-uuid-1"


def test_uuid_round_trips_via_model_dump_json() -> None:
    """JSON serialization must include uuid at every level."""
    exam_json = ExamResponse.model_validate(_exam_obj()).model_dump(mode="json")
    assert exam_json["uuid"] == "exam-uuid-1"
    question_json = QuestionResponse.model_validate(_question_obj()).model_dump(mode="json")
    assert question_json["uuid"] == "question-uuid-1"
    answer_json = AnswerResponse.model_validate(_answer_obj()).model_dump(mode="json")
    assert answer_json["uuid"] == "answer-uuid-1"
