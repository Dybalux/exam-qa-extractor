"""Tests for the SPA-facing ``/api/v1/ui`` endpoints (dashboard + practice)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer import Answer
from app.models.exam import Exam
from app.models.question import Question
from app.models.subject import Subject
from app.models.topic import Topic

BASE = "/api/v1/ui"


async def _seed(session: AsyncSession, n_questions: int = 2) -> list[Question]:
    """Create one exam with ``n_questions`` ready questions (1 correct + 1 wrong)."""
    subject = Subject(name="Sistemas Operativos", slug="sistemas-operativos")
    session.add(subject)
    await session.flush()
    topic = Topic(name="Procesos", slug="processes", subject_id=subject.id)
    session.add(topic)
    exam = Exam(partial_number=1, subject_id=subject.id)
    session.add(exam)
    await session.flush()

    questions = []
    for i in range(n_questions):
        q = Question(exam_id=exam.id, question_text=f"Question {i}?", topic_id=topic.id)
        session.add(q)
        await session.flush()
        session.add(
            Answer(
                question_id=q.id,
                answer_text="right",
                answer_type="correct",
                explanation="Because.",
            )
        )
        session.add(
            Answer(question_id=q.id, answer_text="wrong", answer_type="incorrect")
        )
        questions.append(q)
    await session.commit()
    return questions


async def _start(client: AsyncClient, **overrides) -> dict:
    payload = {"mode": "random", "total_questions": 10, **overrides}
    response = await client.post(f"{BASE}/practice/sessions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _pick(question: dict, text: str) -> int:
    return next(a["id"] for a in question["answers"] if a["text"] == text)


@pytest.mark.asyncio
async def test_dashboard_empty(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data["stats"]["total_questions"] == 0
    assert data["exams"] == []
    assert data["history"] == []
    assert "session_id" in response.cookies


@pytest.mark.asyncio
async def test_dashboard_with_data(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    data = (await client.get(f"{BASE}/dashboard")).json()
    assert data["stats"]["total_exams"] == 1
    assert data["stats"]["questions_ready_for_practice"] == 2
    assert data["exams"][0]["partial_number"] == 1
    assert data["progress"]["by_topic"]["processes"]["ready"] == 2


@pytest.mark.asyncio
async def test_practice_options(client: AsyncClient, db_session: AsyncSession) -> None:
    await _seed(db_session)
    data = (await client.get(f"{BASE}/practice/options")).json()
    assert "random" in data["modes"]
    assert data["exams"][0]["partial_number"] == 1
    assert data["topics"] == [{"slug": "processes", "name": "Procesos"}]


@pytest.mark.asyncio
async def test_start_without_questions_is_422(client: AsyncClient) -> None:
    response = await client.post(
        f"{BASE}/practice/sessions", json={"mode": "random", "total_questions": 5}
    )
    assert response.status_code == 422
    assert "No hay preguntas disponibles" in response.json()["detail"]


@pytest.mark.asyncio
async def test_error_review_without_mistakes_is_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    response = await client.post(
        f"{BASE}/practice/sessions", json={"mode": "error_review"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_full_flow_answer_skip_results(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session, n_questions=2)
    session = await _start(client)
    sid = session["session_id"]
    assert session["total_questions"] == 2

    # First question: answer wrongly -> feedback reveals the right one.
    current = (await client.get(f"{BASE}/practice/sessions/{sid}/current")).json()
    q1 = current["question"]
    assert {a["text"] for a in q1["answers"]} == {"right", "wrong"}
    # Choices must not leak which one is correct.
    assert all(set(a) == {"id", "text"} for a in q1["answers"])

    fb = (
        await client.post(
            f"{BASE}/practice/sessions/{sid}/answer",
            json={
                "question_id": q1["id"],
                "selected_answer_id": _pick(q1, "wrong"),
                "time_spent_seconds": 3,
            },
        )
    ).json()
    assert fb["is_correct"] is False
    assert fb["correct_answer_id"] == _pick(q1, "right")
    assert fb["correct_answer_text"] == "right"
    assert fb["explanation"] == "Because."
    assert fb["session"]["incorrect_count"] == 1

    # Second question: skip it.
    q2 = (await client.get(f"{BASE}/practice/sessions/{sid}/current")).json()[
        "question"
    ]
    assert q2["id"] != q1["id"]
    skip = await client.post(
        f"{BASE}/practice/sessions/{sid}/skip",
        json={"question_id": q2["id"], "time_spent_seconds": 1},
    )
    assert skip.status_code == 200
    assert skip.json()["session"]["skipped_count"] == 1

    # Nothing left: session completes and no question is returned.
    done = (await client.get(f"{BASE}/practice/sessions/{sid}/current")).json()
    assert done["question"] is None
    assert done["session"]["is_completed"] is True

    results = (await client.get(f"{BASE}/practice/sessions/{sid}/results")).json()
    assert results["is_completed"] is True
    assert results["incorrect_count"] == 1
    assert results["skipped_count"] == 1
    assert len(results["responses"]) == 2
    skipped = next(r for r in results["responses"] if r["skipped"])
    assert skipped["question_id"] == q2["id"]

    history = (await client.get(f"{BASE}/dashboard")).json()["history"]
    assert [h["session_id"] for h in history] == [sid]


@pytest.mark.asyncio
async def test_correct_answer_feedback(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session, n_questions=1)
    sid = (await _start(client))["session_id"]
    q = (await client.get(f"{BASE}/practice/sessions/{sid}/current")).json()["question"]
    fb = (
        await client.post(
            f"{BASE}/practice/sessions/{sid}/answer",
            json={"question_id": q["id"], "selected_answer_id": _pick(q, "right")},
        )
    ).json()
    assert fb["is_correct"] is True
    assert fb["session"]["correct_count"] == 1


@pytest.mark.asyncio
async def test_duplicate_answer_is_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session, n_questions=2)
    sid = (await _start(client))["session_id"]
    q = (await client.get(f"{BASE}/practice/sessions/{sid}/current")).json()["question"]
    body = {"question_id": q["id"], "selected_answer_id": _pick(q, "right")}
    assert (
        await client.post(f"{BASE}/practice/sessions/{sid}/answer", json=body)
    ).status_code == 200
    again = await client.post(f"{BASE}/practice/sessions/{sid}/answer", json=body)
    assert again.status_code == 422


@pytest.mark.asyncio
async def test_unknown_session_is_404(client: AsyncClient) -> None:
    assert (
        await client.get(f"{BASE}/practice/sessions/999/current")
    ).status_code == 404
    assert (
        await client.get(f"{BASE}/practice/sessions/999/results")
    ).status_code == 404


@pytest.mark.asyncio
async def test_incorrect_answer_explanation_combination(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    questions = await _seed(db_session, n_questions=1)
    q = questions[0]
    answers_res = await db_session.execute(
        select(Answer).where(Answer.question_id == q.id)
    )
    for a in answers_res.scalars().all():
        if a.answer_type == "correct":
            a.explanation = "Kernel saves A and restores B."
        else:
            a.explanation = "Incorrect because it ignores return step."
    await db_session.commit()

    session = await _start(client)
    sid = session["session_id"]
    current = (await client.get(f"{BASE}/practice/sessions/{sid}/current")).json()[
        "question"
    ]
    wrong_id = _pick(current, "wrong")

    fb = (
        await client.post(
            f"{BASE}/practice/sessions/{sid}/answer",
            json={"question_id": q.id, "selected_answer_id": wrong_id},
        )
    ).json()

    assert fb["is_correct"] is False
    assert (
        fb["explanation"]
        == "Incorrect because it ignores return step.\n\nKernel saves A and restores B."
    )


@pytest.mark.asyncio
async def test_ui_practice_complete_endpoint(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session, n_questions=2)
    session = await _start(client)
    sid = session["session_id"]

    res = await client.post(f"{BASE}/practice/sessions/{sid}/complete")
    assert res.status_code == 200
    data = res.json()
    assert data["is_completed"] is True

    # Calling complete on an already completed session is idempotent
    res2 = await client.post(f"{BASE}/practice/sessions/{sid}/complete")
    assert res2.status_code == 200
    assert res2.json()["is_completed"] is True


@pytest.mark.asyncio
async def test_exam_paper_endpoint_and_answer_change(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session, n_questions=3)
    session = await _start(client, mode="exam_simulation", total_questions=3)
    sid = session["session_id"]

    res = await client.get(f"{BASE}/practice/sessions/{sid}/paper")
    assert res.status_code == 200
    paper = res.json()
    assert len(paper["questions"]) == 3
    assert paper["session"]["mode"] == "exam_simulation"

    q1 = paper["questions"][0]
    wrong_id = _pick(q1, "wrong")
    right_id = _pick(q1, "right")

    # Answer question 1 with wrong answer
    ans_res = await client.post(
        f"{BASE}/practice/sessions/{sid}/answer",
        json={"question_id": q1["id"], "selected_answer_id": wrong_id},
    )
    assert ans_res.status_code == 200
    assert ans_res.json()["session"]["incorrect_count"] == 1
    assert ans_res.json()["session"]["correct_count"] == 0

    # In exam_simulation mode, user navigates back and changes answer to right
    change_res = await client.post(
        f"{BASE}/practice/sessions/{sid}/answer",
        json={"question_id": q1["id"], "selected_answer_id": right_id},
    )
    assert change_res.status_code == 200
    assert change_res.json()["session"]["correct_count"] == 1
    assert change_res.json()["session"]["incorrect_count"] == 0

    # Paper reflects new selection
    paper2 = (await client.get(f"{BASE}/practice/sessions/{sid}/paper")).json()
    assert paper2["questions"][0]["selected_answer_id"] == right_id


@pytest.mark.asyncio
async def test_ui_practice_complete_with_anti_cheat_lockout(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session, n_questions=2)
    session = await _start(client, mode="exam_simulation", total_questions=2)
    sid = session["session_id"]

    # Complete with anti-cheat lockout reason
    res = await client.post(
        f"{BASE}/practice/sessions/{sid}/complete",
        json={"lockout_reason": "focus_lost"},
    )
    assert res.status_code == 200
    assert res.json()["is_completed"] is True

    # Results include the lockout_reason
    res_results = await client.get(f"{BASE}/practice/sessions/{sid}/results")
    assert res_results.status_code == 200
    results_data = res_results.json()
    assert results_data["is_completed"] is True
    assert results_data["lockout_reason"] == "focus_lost"


@pytest.mark.asyncio
async def test_ui_practice_session_metadata(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session, n_questions=3)
    session = await _start(client, mode="random", total_questions=3)
    sid = session["session_id"]

    res = await client.get(f"{BASE}/practice/sessions/{sid}")
    assert res.status_code == 200
    meta = res.json()
    assert meta["session_id"] == sid
    assert meta["mode"] == "random"
    assert meta["total_questions"] == 3
    assert meta["questions_answered"] == 0
    assert meta["is_completed"] is False


@pytest.mark.asyncio
async def test_exam_simulation_results_includes_all_blueprint_questions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session, n_questions=3)
    session = await _start(client, mode="exam_simulation", total_questions=3)
    sid = session["session_id"]

    # Get paper
    paper = (await client.get(f"{BASE}/practice/sessions/{sid}/paper")).json()
    assert len(paper["questions"]) == 3
    q1 = paper["questions"][0]
    right_id = _pick(q1, "right")

    # Only answer 1 of 3 questions (correctly)
    ans_res = await client.post(
        f"{BASE}/practice/sessions/{sid}/answer",
        json={"question_id": q1["id"], "selected_answer_id": right_id},
    )
    assert ans_res.status_code == 200

    # Complete session explicitly
    comp_res = await client.post(f"{BASE}/practice/sessions/{sid}/complete")
    assert comp_res.status_code == 200

    # Get results
    res_results = await client.get(f"{BASE}/practice/sessions/{sid}/results")
    assert res_results.status_code == 200
    results = res_results.json()

    assert results["total_questions"] == 3
    assert results["questions_answered"] == 1
    assert results["correct_count"] == 1
    assert results["incorrect_count"] == 0
    assert results["skipped_count"] == 2
    assert results["accuracy"] == pytest.approx(33.33, rel=1e-2)
    assert len(results["responses"]) == 3

    # First question is answered
    assert results["responses"][0]["question_id"] == q1["id"]
    assert results["responses"][0]["selected_answer_id"] == right_id
    assert results["responses"][0]["is_correct"] is True
    assert results["responses"][0]["skipped"] is False

    # Second and third questions are unattempted/skipped
    for r in results["responses"][1:]:
        assert r["selected_answer_id"] is None
        assert r["is_correct"] is False
        assert r["skipped"] is True
        assert r["is_skipped"] is True


@pytest.mark.asyncio
async def test_error_review_with_explicit_question_ids_reviews_exactly_those(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    questions = await _seed(db_session, n_questions=3)
    chosen = {questions[0].id, questions[1].id}

    session = await _start(
        client,
        mode="error_review",
        total_questions=2,
        question_ids=sorted(chosen),
    )
    assert session["total_questions"] == 2

    seen: set[int] = set()
    for _ in range(2):
        current = (
            await client.get(
                f"{BASE}/practice/sessions/{session['session_id']}/current"
            )
        ).json()
        question = current["question"]
        assert question is not None
        seen.add(question["id"])
        answered = await client.post(
            f"{BASE}/practice/sessions/{session['session_id']}/answer",
            json={
                "question_id": question["id"],
                "selected_answer_id": _pick(question, "right"),
                "time_spent_seconds": 1,
            },
        )
        assert answered.status_code == 200, answered.text

    assert seen == chosen
    done = (
        await client.get(f"{BASE}/practice/sessions/{session['session_id']}/current")
    ).json()
    assert done["question"] is None


@pytest.mark.asyncio
async def test_start_on_empty_exam_returns_friendly_spanish_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    questions = await _seed(db_session, n_questions=1)
    empty = Exam(
        partial_number=4,
        subject_id=(await db_session.get(Exam, questions[0].exam_id)).subject_id,
    )
    db_session.add(empty)
    await db_session.commit()

    response = await client.post(
        f"{BASE}/practice/sessions",
        json={"mode": "random", "exam_id": empty.id, "total_questions": 5},
    )
    assert response.status_code == 422
    assert "No hay preguntas disponibles" in response.json()["detail"]
