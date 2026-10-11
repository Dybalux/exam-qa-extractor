"""Integration tests for practice creation with error_review mode (SPA API)."""

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AnswerType, PracticeMode
from app.models.answer import Answer
from app.models.exam import Exam
from app.models.practice_response import PracticeResponse
from app.models.practice_session import PracticeSession
from app.models.question import Question
from app.models.topic import Topic

SESSIONS = "/api/v1/ui/practice/sessions"


async def _get_other_topic(db_session: AsyncSession, default_subject) -> Topic:
    """Resolve the 'other' topic for *default_subject*, avoiding lazy-load
    on the relationship."""
    result = await db_session.execute(
        select(Topic).where(
            Topic.slug == "other",
            Topic.subject_id == default_subject.id,
        )
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_error_review_with_failures_creates_session(
    client: AsyncClient,
    db_session: AsyncSession,
    default_subject,
) -> None:
    """POST /practice with mode=error_review + existing failures redirects
    to /practice/{id}/play and creates a session restricted to failed questions."""
    user_session_id = "int-test-user-1"
    client.cookies.set("session_id", user_session_id)

    topic = await _get_other_topic(db_session, default_subject)

    # Seed: exam, question with correct answer, and a failed response
    exam = Exam(partial_number=1, subject_id=default_subject.id)
    db_session.add(exam)
    await db_session.flush()

    question = Question(
        exam_id=exam.id,
        question_text="Integration test question",
        topic_id=topic.id,
        is_corrected=True,
    )
    db_session.add(question)
    await db_session.flush()

    correct_answer = Answer(
        question_id=question.id,
        answer_text="The right answer",
        answer_type=AnswerType.CORRECT.value,
        display_order=0,
    )
    db_session.add(correct_answer)
    await db_session.flush()

    # Seed a SECOND ready question in the same exam with a correct answer
    # but NO failed response. This lets us prove error_review excludes
    # non-failed questions rather than just returning whatever exists.
    other_question = Question(
        exam_id=exam.id,
        question_text="Never failed other question",
        topic_id=topic.id,
        is_corrected=True,
    )
    db_session.add(other_question)
    await db_session.flush()

    other_correct = Answer(
        question_id=other_question.id,
        answer_text="Other right answer",
        answer_type=AnswerType.CORRECT.value,
        display_order=0,
    )
    db_session.add(other_correct)
    await db_session.flush()

    # Record a failed response for this user (only for `question`)
    prior_session = PracticeSession(
        user_session_id=user_session_id,
        mode=PracticeMode.RANDOM.value,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(prior_session)
    await db_session.flush()

    db_session.add(
        PracticeResponse(
            session_id=prior_session.id,
            question_id=question.id,
            selected_answer_id=correct_answer.id,
            is_correct=False,
            answered_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    # Create the error_review session through the SPA endpoint
    resp = await client.post(
        SESSIONS, json={"mode": "error_review", "total_questions": 10}
    )
    assert resp.status_code == 201, resp.text
    session_id = resp.json()["session_id"]

    current = (await client.get(f"{SESSIONS}/{session_id}/current")).json()
    assert current["question"]["text"] == question.question_text

    # Answering it exhausts the pool: the never-failed question must NOT show
    # up, which proves error_review restricts the pool to failed questions.
    picked = current["question"]["answers"][0]["id"]
    answered = await client.post(
        f"{SESSIONS}/{session_id}/answer",
        json={
            "question_id": question.id,
            "selected_answer_id": picked,
            "time_spent_seconds": 1,
        },
    )
    assert answered.status_code == 200
    after = (await client.get(f"{SESSIONS}/{session_id}/current")).json()
    assert after["question"] is None


@pytest.mark.asyncio
async def test_error_review_no_failures_is_friendly_422(
    client: AsyncClient,
    db_session: AsyncSession,
    default_subject,
) -> None:
    """Starting error_review with no failures returns a friendly 422.

    A ready question (with a correct answer) is seeded but has NO failed
    response, so the empty ``question_ids=[]`` path is exercised for real
    rather than being masked by an empty question pool.
    """
    user_session_id = "int-test-user-no-fails"
    client.cookies.set("session_id", user_session_id)

    topic = await _get_other_topic(db_session, default_subject)

    # Seed a ready question with a correct answer but no failed response
    exam = Exam(partial_number=1, subject_id=default_subject.id)
    db_session.add(exam)
    await db_session.flush()

    question = Question(
        exam_id=exam.id,
        question_text="Ready but never-failed question",
        topic_id=topic.id,
        is_corrected=True,
    )
    db_session.add(question)
    await db_session.flush()

    correct_answer = Answer(
        question_id=question.id,
        answer_text="The right answer",
        answer_type=AnswerType.CORRECT.value,
        display_order=0,
    )
    db_session.add(correct_answer)
    await db_session.commit()

    resp = await client.post(
        SESSIONS, json={"mode": "error_review", "total_questions": 10}
    )

    assert resp.status_code == 422
    assert resp.json()["detail"] == "Todavía no tienes errores para revisar."


@pytest.mark.asyncio
async def test_error_review_with_exam_filter(
    client: AsyncClient,
    db_session: AsyncSession,
    default_subject,
) -> None:
    """Starting error_review with an exam_id filter restricts to
    failed questions from that exam only."""
    user_session_id = "int-test-user-2"
    client.cookies.set("session_id", user_session_id)

    topic = await _get_other_topic(db_session, default_subject)

    # Exam E1 with a failed question
    exam1 = Exam(partial_number=1, subject_id=default_subject.id)
    db_session.add(exam1)
    await db_session.flush()

    q1 = Question(
        exam_id=exam1.id,
        question_text="E1 question",
        topic_id=topic.id,
        is_corrected=True,
    )
    db_session.add(q1)
    await db_session.flush()

    a1 = Answer(
        question_id=q1.id,
        answer_text="E1 answer",
        answer_type=AnswerType.CORRECT.value,
        display_order=0,
    )
    db_session.add(a1)
    await db_session.flush()

    # Exam E2 with no failed questions
    exam2 = Exam(partial_number=2, subject_id=default_subject.id)
    db_session.add(exam2)
    await db_session.flush()

    q2 = Question(
        exam_id=exam2.id,
        question_text="E2 question",
        topic_id=topic.id,
        is_corrected=True,
    )
    db_session.add(q2)
    await db_session.flush()

    a2 = Answer(
        question_id=q2.id,
        answer_text="E2 answer",
        answer_type=AnswerType.CORRECT.value,
        display_order=0,
    )
    db_session.add(a2)
    await db_session.flush()

    # Record a failed response only for E1's question
    prior_session = PracticeSession(
        user_session_id=user_session_id,
        mode=PracticeMode.RANDOM.value,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(prior_session)
    await db_session.flush()

    db_session.add(
        PracticeResponse(
            session_id=prior_session.id,
            question_id=q1.id,
            selected_answer_id=a1.id,
            is_correct=False,
            answered_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    # exam_id=E2 (no failures there) -> friendly 422
    resp2 = await client.post(
        SESSIONS,
        json={"mode": "error_review", "exam_id": exam2.id, "total_questions": 10},
    )
    assert resp2.status_code == 422
    assert "errores para revisar" in resp2.json()["detail"]

    # exam_id=E1 -> session is created
    resp1 = await client.post(
        SESSIONS,
        json={"mode": "error_review", "exam_id": exam1.id, "total_questions": 10},
    )
    assert resp1.status_code == 201
