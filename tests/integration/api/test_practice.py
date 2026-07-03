"""Integration tests for practice creation with error_review mode."""

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

    # POST: create error_review session
    resp = await client.post(
        "/practice",
        data={"mode": "error_review", "total_questions": "10"},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    assert "/practice/" in resp.headers["location"]
    assert resp.headers["location"].endswith("/play")

    # The response sets a cookie — capture it for the redirect follow
    new_cookies = resp.cookies
    if new_cookies:
        client.cookies.update(new_cookies)

    # Follow redirect to play and verify the session contains our failed question
    play_resp = await client.get(
        resp.headers["location"],
        follow_redirects=False,
    )
    assert play_resp.status_code == 200
    assert question.question_text in play_resp.text
    # The non-failed question must NOT appear — proves error_review
    # restricts the pool to failed questions rather than returning any.
    assert other_question.question_text not in play_resp.text


@pytest.mark.asyncio
async def test_error_review_no_failures_flash_redirect(
    client: AsyncClient,
    db_session: AsyncSession,
    default_subject,
) -> None:
    """POST /practice with mode=error_review + no failures redirects to
    /practice with flash message.

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
        "/practice",
        data={"mode": "error_review", "total_questions": "10"},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    location = resp.headers["location"]
    assert "/practice" in location
    # Flash message should be in query params
    assert "message=Todav%C3%ADa" in location or "message=Todav%C3" in location

    # Follow redirect and verify flash message appears on the page
    follow = await client.get(
        location,
        follow_redirects=False,
    )
    assert follow.status_code == 200
    assert "Todavía no tenés errores para revisar" in follow.text


@pytest.mark.asyncio
async def test_error_review_with_exam_filter(
    client: AsyncClient,
    db_session: AsyncSession,
    default_subject,
) -> None:
    """POST /practice with mode=error_review + exam_id filter restricts to
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

    # POST with exam_id=E2 (no failures there) → should redirect with flash
    resp2 = await client.post(
        "/practice",
        data={
            "mode": "error_review",
            "exam_id": str(exam2.id),
            "total_questions": "10",
        },
        follow_redirects=False,
    )
    assert resp2.status_code == 303
    assert "/practice" in resp2.headers["location"]
    assert "message=" in resp2.headers["location"]

    # POST with exam_id=E1 → should succeed and create session
    resp1 = await client.post(
        "/practice",
        data={
            "mode": "error_review",
            "exam_id": str(exam1.id),
            "total_questions": "10",
        },
        follow_redirects=False,
    )
    assert resp1.status_code == 303
    assert "/practice/" in resp1.headers["location"]
    assert resp1.headers["location"].endswith("/play")
