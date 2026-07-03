"""Unit tests for PracticeService error_review mode."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AnswerType, PracticeMode
from app.core.exceptions import ValidationError
from app.models.answer import Answer
from app.models.exam import Exam
from app.models.practice_response import PracticeResponse
from app.models.practice_session import PracticeSession
from app.models.question import Question
from app.models.topic import Topic
from app.services.practice_service import PracticeService


@pytest.mark.asyncio
async def test_get_failed_question_ids_deduplicated(
    db_session: AsyncSession,
    default_subject,
) -> None:
    """_get_failed_question_ids returns deduplicated incorrect question IDs,
    excluding correct and skipped responses."""
    service = PracticeService(db_session)
    user_session_id = "test-user-failures"

    # Query the 'other' topic directly (avoids lazy-load on default_subject)
    result = await db_session.execute(
        select(Topic).where(
            Topic.slug == "other", Topic.subject_id == default_subject.id
        )
    )
    topic = result.scalar_one()

    # Create exam and question with correct answer
    exam = Exam(partial_number=1, subject_id=default_subject.id)
    db_session.add(exam)
    await db_session.flush()

    question = Question(
        exam_id=exam.id,
        question_text="Test question?",
        topic_id=topic.id,
        is_corrected=True,
    )
    db_session.add(question)
    await db_session.flush()

    correct_answer = Answer(
        question_id=question.id,
        answer_text="Correct answer",
        answer_type=AnswerType.CORRECT.value,
        display_order=0,
    )
    db_session.add(correct_answer)
    await db_session.flush()

    # Create two practice sessions for the same user
    session1 = PracticeSession(
        user_session_id=user_session_id,
        mode=PracticeMode.RANDOM.value,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(session1)
    await db_session.flush()

    session2 = PracticeSession(
        user_session_id=user_session_id,
        mode=PracticeMode.RANDOM.value,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(session2)
    await db_session.flush()

    # Incorrect response in session1
    db_session.add(
        PracticeResponse(
            session_id=session1.id,
            question_id=question.id,
            selected_answer_id=correct_answer.id,
            is_correct=False,
            answered_at=datetime.now(timezone.utc),
        )
    )
    # Incorrect response for same question in session2 (duplicate ID)
    db_session.add(
        PracticeResponse(
            session_id=session2.id,
            question_id=question.id,
            selected_answer_id=correct_answer.id,
            is_correct=False,
            answered_at=datetime.now(timezone.utc),
        )
    )
    await db_session.flush()

    # Create another question for completeness
    q2 = Question(
        exam_id=exam.id,
        question_text="Another question?",
        topic_id=topic.id,
        is_corrected=True,
    )
    db_session.add(q2)
    await db_session.flush()

    correct2 = Answer(
        question_id=q2.id,
        answer_text="OK",
        answer_type=AnswerType.CORRECT.value,
        display_order=0,
    )
    db_session.add(correct2)
    await db_session.flush()

    # Correct response — should be excluded
    db_session.add(
        PracticeResponse(
            session_id=session1.id,
            question_id=q2.id,
            selected_answer_id=correct2.id,
            is_correct=True,
            answered_at=datetime.now(timezone.utc),
        )
    )
    # Skipped response (is_correct=None) — should be excluded
    db_session.add(
        PracticeResponse(
            session_id=session1.id,
            question_id=q2.id,
            selected_answer_id=None,
            is_correct=None,
            answered_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    result = await service._get_failed_question_ids(user_session_id)

    # Only the incorrect question IDs, deduplicated
    assert len(result) == 1
    assert result[0] == question.id


@pytest.mark.asyncio
async def test_create_session_error_review_no_failures(
    db_session: AsyncSession,
    default_subject,
) -> None:
    """create_session with mode='error_review' and no failed responses
    raises ValidationError with expected message.

    A ready question (with a correct answer) is seeded but has NO failed
    response, so the empty ``question_ids=[]`` path is exercised for real
    rather than being masked by an empty question pool.
    """
    service = PracticeService(db_session)

    # Resolve the 'other' topic directly (avoids lazy-load on default_subject)
    result = await db_session.execute(
        select(Topic).where(
            Topic.slug == "other", Topic.subject_id == default_subject.id
        )
    )
    topic = result.scalar_one()

    # Seed a ready question with a correct answer but no failed response
    exam = Exam(partial_number=1, subject_id=default_subject.id)
    db_session.add(exam)
    await db_session.flush()

    question = Question(
        exam_id=exam.id,
        question_text="Ready but never-failed question?",
        topic_id=topic.id,
        is_corrected=True,
    )
    db_session.add(question)
    await db_session.flush()

    correct_answer = Answer(
        question_id=question.id,
        answer_text="Correct answer",
        answer_type=AnswerType.CORRECT.value,
        display_order=0,
    )
    db_session.add(correct_answer)
    await db_session.commit()

    with pytest.raises(ValidationError) as exc_info:
        await service.create_session(
            user_session_id="new-user-no-failures",
            mode=PracticeMode.ERROR_REVIEW.value,
        )

    assert "No questions with previous errors found." in str(exc_info.value)
