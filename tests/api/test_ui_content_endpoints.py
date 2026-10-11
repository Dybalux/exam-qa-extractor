"""Tests for the SPA-facing exams / questions / analytics endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_ocr_service, get_storage_service
from app.main import SPAStaticFiles, app
from app.models.answer import Answer
from app.models.exam import Exam
from app.models.question import Question
from app.models.subject import Subject
from app.models.topic import Topic

BASE = "/api/v1/ui"


async def _seed(session: AsyncSession) -> tuple[Exam, list[Question]]:
    """One exam with a ready question and an unanswered, low-confidence one."""
    subject = Subject(name="Sistemas Operativos", slug="sistemas-operativos")
    session.add(subject)
    await session.flush()
    topic = Topic(name="Procesos", slug="processes", subject_id=subject.id)
    session.add_all([topic, Topic(name="Otros", slug="other", subject_id=subject.id)])
    exam = Exam(partial_number=1, subject_id=subject.id, topic_tags="procesos")
    session.add(exam)
    await session.flush()

    ready = Question(
        exam_id=exam.id,
        question_text="¿Qué es un proceso?",
        confidence_score=95.0,
        topic_id=topic.id,
    )
    pending = Question(
        exam_id=exam.id,
        question_text="Texto OCR dudoso",
        extracted_text="Texto OCR dudoso",
        confidence_score=30.0,
        topic_id=topic.id,
    )
    session.add_all([ready, pending])
    await session.flush()
    session.add(
        Answer(
            question_id=ready.id,
            answer_text="Un programa en ejecución",
            answer_type="correct",
        )
    )
    session.add(
        Answer(question_id=ready.id, answer_text="Un archivo", answer_type="incorrect")
    )
    await session.commit()
    return exam, [ready, pending]


# ── Exams ────────────────────────────────────────────────────


async def test_exam_list_includes_question_count(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed(db_session)
    body = (await client.get(f"{BASE}/exams")).json()
    assert len(body) == 1
    assert body[0]["question_count"] == 2
    assert (await client.get(f"{BASE}/exams?partial_number=2")).json() == []


async def test_exam_create_update_delete(client: AsyncClient, db_session: AsyncSession):
    created = await client.post(
        f"{BASE}/exams",
        json={"partial_number": 2, "exam_date": "2025-05-01", "topic_tags": "memoria"},
    )
    assert created.status_code == 201
    exam_id = created.json()["id"]
    assert created.json()["exam_date"] == "2025-05-01"

    updated = await client.put(f"{BASE}/exams/{exam_id}", json={"partial_number": 3})
    assert updated.status_code == 200
    assert updated.json()["partial_number"] == 3
    assert updated.json()["topic_tags"] == ""

    assert (await client.delete(f"{BASE}/exams/{exam_id}")).status_code == 204
    assert (await client.get(f"{BASE}/exams/{exam_id}")).status_code == 404


async def test_exam_create_rejects_invalid_partial(client: AsyncClient):
    response = await client.post(f"{BASE}/exams", json={"partial_number": 9})
    assert response.status_code == 422


async def test_exam_detail_has_coverage_and_questions(
    client: AsyncClient, db_session: AsyncSession
):
    exam, _ = await _seed(db_session)
    body = (await client.get(f"{BASE}/exams/{exam.id}")).json()
    assert body["exam"]["partial_number"] == 1
    assert body["coverage"]["total_questions"] == 2
    assert body["coverage"]["ready_for_practice"] == 1
    assert {q["is_ready_for_practice"] for q in body["questions"]} == {True, False}


async def test_exam_detail_without_questions(client: AsyncClient):
    exam_id = (await client.post(f"{BASE}/exams", json={"partial_number": 1})).json()[
        "id"
    ]
    body = (await client.get(f"{BASE}/exams/{exam_id}")).json()
    assert body["questions"] == []
    assert body["coverage"]["total_questions"] == 0
    assert body["coverage"]["readiness_pct"] == 0


async def test_exam_detail_missing_is_404(client: AsyncClient):
    assert (await client.get(f"{BASE}/exams/999")).status_code == 404


async def test_exam_delete_with_questions_needs_force(
    client: AsyncClient, db_session: AsyncSession
):
    exam, _ = await _seed(db_session)
    assert (await client.delete(f"{BASE}/exams/{exam.id}")).status_code == 409
    assert (
        await client.delete(f"{BASE}/exams/{exam.id}?force=true")
    ).status_code == 204


# ── Manual question / correction / delete ────────────────────


async def test_manual_question_creates_ready_corrected_question(
    client: AsyncClient, db_session: AsyncSession
):
    exam, _ = await _seed(db_session)
    response = await client.post(
        f"{BASE}/exams/{exam.id}/questions",
        json={
            "question_text": "¿Qué es un hilo?",
            "topic": "processes",
            "correct_answer_text": "Una unidad de ejecución",
            "explanation": "Vive dentro de un proceso.",
        },
    )
    assert response.status_code == 201
    detail = (await client.get(f"{BASE}/questions/{response.json()['id']}")).json()
    assert detail["question"]["is_corrected"] is True
    assert detail["question"]["is_ready_for_practice"] is True
    assert detail["answers"][0]["is_correct"] is True
    assert detail["answers"][0]["explanation"] == "Vive dentro de un proceso."


async def test_manual_question_validation(
    client: AsyncClient, db_session: AsyncSession
):
    exam, _ = await _seed(db_session)
    empty = await client.post(
        f"{BASE}/exams/{exam.id}/questions",
        json={"question_text": "", "topic": "processes", "correct_answer_text": "x"},
    )
    assert empty.status_code == 422
    bad_topic = await client.post(
        f"{BASE}/exams/{exam.id}/questions",
        json={"question_text": "q", "topic": "nope", "correct_answer_text": "x"},
    )
    assert bad_topic.status_code == 422
    missing_exam = await client.post(
        f"{BASE}/exams/999/questions",
        json={"question_text": "q", "topic": "processes", "correct_answer_text": "x"},
    )
    assert missing_exam.status_code == 404


async def test_question_correct_and_delete(
    client: AsyncClient, db_session: AsyncSession
):
    _, (_, pending) = await _seed(db_session)
    corrected = await client.post(
        f"{BASE}/questions/{pending.id}/correct",
        json={"corrected_text": "Texto corregido", "notes": "Se arregló la tilde"},
    )
    assert corrected.status_code == 200
    assert corrected.json()["question_text"] == "Texto corregido"
    assert corrected.json()["is_corrected"] is True

    detail = (await client.get(f"{BASE}/questions/{pending.id}")).json()
    assert detail["correction_notes"] == "Se arregló la tilde"
    assert detail["extracted_text"] == "Texto OCR dudoso"

    assert (await client.delete(f"{BASE}/questions/{pending.id}")).status_code == 204
    assert (await client.get(f"{BASE}/questions/{pending.id}")).status_code == 404


async def test_question_detail_missing_is_404(client: AsyncClient):
    assert (await client.get(f"{BASE}/questions/999")).status_code == 404


# ── Question list / review queue ─────────────────────────────


async def test_question_list_filters(client: AsyncClient, db_session: AsyncSession):
    exam, _ = await _seed(db_session)
    everything = (await client.get(f"{BASE}/questions")).json()
    assert len(everything["questions"]) == 2
    assert {t["slug"] for t in everything["topics"]} == {"processes", "other"}
    assert len(everything["exams"]) == 1

    ready = (await client.get(f"{BASE}/questions?is_ready=true")).json()
    assert [q["question_text"] for q in ready["questions"]] == ["¿Qué es un proceso?"]

    unready = (
        await client.get(f"{BASE}/questions?is_ready=false&is_corrected=false")
    ).json()
    assert [q["question_text"] for q in unready["questions"]] == ["Texto OCR dudoso"]

    other_exam = (await client.get(f"{BASE}/questions?exam_id={exam.id + 1}")).json()
    assert other_exam["questions"] == []
    by_topic = (await client.get(f"{BASE}/questions?topic=processes")).json()
    assert len(by_topic["questions"]) == 2


async def test_review_queue_lists_low_confidence_only(
    client: AsyncClient, db_session: AsyncSession
):
    exam, _ = await _seed(db_session)
    body = (await client.get(f"{BASE}/questions/review")).json()
    assert [q["question_text"] for q in body["questions"]] == ["Texto OCR dudoso"]
    assert len(body["exams"]) == 1
    assert (await client.get(f"{BASE}/questions/review?exam_id={exam.id + 1}")).json()[
        "questions"
    ] == []


# ── OCR upload (OCR and storage are faked) ───────────────────


@dataclass
class _FakeExtracted:
    text: str
    order: int
    confidence: float
    requires_review: bool


@dataclass
class _FakeOCRResult:
    questions: list[_FakeExtracted]


class _FakeOCR:
    def __init__(self, questions: list[_FakeExtracted]):
        self._questions = questions

    async def extract_from_path(self, _path: Path) -> _FakeOCRResult:
        return _FakeOCRResult(self._questions)


class _FakeStorage:
    async def save_file(self, file_data, original_filename: str, exam_id: int):
        @dataclass
        class _Saved:
            storage_path: Path = Path("unused")

        return _Saved()


@pytest.fixture
def fake_upload():
    def _install(questions: list[_FakeExtracted]) -> None:
        app.dependency_overrides[get_ocr_service] = lambda: _FakeOCR(questions)
        app.dependency_overrides[get_storage_service] = lambda: _FakeStorage()

    yield _install
    app.dependency_overrides.pop(get_ocr_service, None)
    app.dependency_overrides.pop(get_storage_service, None)


async def test_upload_creates_questions(
    client: AsyncClient, db_session: AsyncSession, fake_upload
):
    exam, _ = await _seed(db_session)
    fake_upload(
        [
            _FakeExtracted("Primera pregunta", 1, 90.0, False),
            _FakeExtracted("Segunda pregunta", 2, 40.0, True),
        ]
    )
    response = await client.post(
        f"{BASE}/exams/{exam.id}/upload",
        files={"file": ("page.png", b"fake-bytes", "image/png")},
        data={"language": "spa"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] == 2
    assert body["needing_review"] == 1
    assert "1 necesitan revisión" in body["message"]
    assert len((await client.get(f"{BASE}/exams/{exam.id}")).json()["questions"]) == 4


async def test_upload_without_extracted_questions_is_422(
    client: AsyncClient, db_session: AsyncSession, fake_upload
):
    exam, _ = await _seed(db_session)
    fake_upload([])
    response = await client.post(
        f"{BASE}/exams/{exam.id}/upload",
        files={"file": ("page.png", b"fake-bytes", "image/png")},
    )
    assert response.status_code == 422
    assert "No se pudieron extraer preguntas" in response.json()["detail"]


async def test_upload_missing_exam_is_404(client: AsyncClient, fake_upload):
    fake_upload([])
    response = await client.post(
        f"{BASE}/exams/999/upload",
        files={"file": ("page.png", b"fake-bytes", "image/png")},
    )
    assert response.status_code == 404


# ── Analytics ────────────────────────────────────────────────


async def test_analytics_overview_and_weak_areas(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed(db_session)
    overview = (await client.get(f"{BASE}/analytics")).json()
    assert overview["stats"]["total_questions"] == 2
    assert overview["stats"]["questions_ready_for_practice"] == 1
    assert "processes" in overview["progress"]["by_topic"]
    assert overview["performance"] == {}

    weak = await client.get(f"{BASE}/analytics/weak-areas?threshold=75")
    assert weak.status_code == 200
    assert weak.json() == {"threshold": 75.0, "weak_areas": [], "history": []}
    assert "session_id" in weak.cookies


async def test_weak_areas_reflect_wrong_answers(
    client: AsyncClient, db_session: AsyncSession
):
    _, (ready, _) = await _seed(db_session)
    session = (
        await client.post(
            f"{BASE}/practice/sessions", json={"mode": "random", "total_questions": 1}
        )
    ).json()
    current = (
        await client.get(f"{BASE}/practice/sessions/{session['session_id']}/current")
    ).json()
    wrong = next(
        a["id"] for a in current["question"]["answers"] if a["text"] == "Un archivo"
    )
    await client.post(
        f"{BASE}/practice/sessions/{session['session_id']}/answer",
        json={
            "question_id": ready.id,
            "selected_answer_id": wrong,
            "time_spent_seconds": 3,
        },
    )
    body = (await client.get(f"{BASE}/analytics/weak-areas")).json()
    assert [w["topic"] for w in body["weak_areas"]] == ["processes"]
    assert body["history"][0]["session_id"] == session["session_id"]
    performance = (await client.get(f"{BASE}/analytics")).json()["performance"]
    assert performance["processes"]["accuracy_pct"] == 0


# ── Answers ──────────────────────────────────────────────────


async def test_answer_create_update_delete(
    client: AsyncClient, db_session: AsyncSession
):
    _, (_, pending) = await _seed(db_session)
    url = f"{BASE}/questions/{pending.id}/answers"

    created = await client.post(
        url,
        json={
            "answer_text": "Respuesta A",
            "answer_type": "correct",
            "explanation": "Porque sí",
            "is_common_misconception": False,
        },
    )
    assert created.status_code == 201, created.text
    answer = created.json()
    assert answer["answer_type"] == "correct"
    assert answer["is_correct"] is True

    updated = await client.put(
        f"{url}/{answer['id']}",
        json={
            "answer_text": "Respuesta B",
            "answer_type": "partial",
            "explanation": "",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["answer_text"] == "Respuesta B"
    assert updated.json()["answer_type"] == "partial"
    assert updated.json()["explanation"] == ""

    assert (await client.delete(f"{url}/{answer['id']}")).status_code == 204
    detail = (await client.get(f"{BASE}/questions/{pending.id}")).json()
    assert detail["answers"] == []


async def test_answer_only_one_correct(client: AsyncClient, db_session: AsyncSession):
    _, (ready, _) = await _seed(db_session)  # `ready` already has a correct answer
    url = f"{BASE}/questions/{ready.id}/answers"

    second = await client.post(
        url, json={"answer_text": "Otra", "answer_type": "correct"}
    )
    assert second.status_code == 409
    assert (
        second.json()["detail"]
        == "Solo puede haber una respuesta correcta por pregunta."
    )

    wrong = await client.post(
        url, json={"answer_text": "Mala", "answer_type": "incorrect"}
    )
    promote = await client.put(
        f"{url}/{wrong.json()['id']}",
        json={"answer_text": "Mala", "answer_type": "correct"},
    )
    assert promote.status_code == 409


async def test_answer_validation_and_ownership(
    client: AsyncClient, db_session: AsyncSession
):
    _, (ready, pending) = await _seed(db_session)
    assert (
        await client.post(
            f"{BASE}/questions/{pending.id}/answers", json={"answer_text": ""}
        )
    ).status_code == 422
    assert (
        await client.post(
            f"{BASE}/questions/{pending.id}/answers",
            json={"answer_text": "x", "answer_type": "bogus"},
        )
    ).status_code == 422
    assert (
        await client.post(f"{BASE}/questions/999/answers", json={"answer_text": "x"})
    ).status_code == 404

    # An answer of `ready` can't be touched through `pending`.
    foreign = (await client.get(f"{BASE}/questions/{ready.id}")).json()["answers"][0][
        "id"
    ]
    assert (
        await client.put(
            f"{BASE}/questions/{pending.id}/answers/{foreign}",
            json={"answer_text": "hack"},
        )
    ).status_code == 404
    assert (
        await client.delete(f"{BASE}/questions/{pending.id}/answers/{foreign}")
    ).status_code == 404


async def test_answer_reorder(client: AsyncClient, db_session: AsyncSession):
    _, (_, pending) = await _seed(db_session)
    url = f"{BASE}/questions/{pending.id}/answers"
    ids = []
    for text in ("Uno", "Dos", "Tres"):
        ids.append((await client.post(url, json={"answer_text": text})).json()["id"])

    # New answers are appended in creation order.
    listed = (await client.get(f"{BASE}/questions/{pending.id}")).json()["answers"]
    assert [a["id"] for a in listed] == ids

    reordered = await client.put(f"{url}/order", json={"ordered_ids": ids[::-1]})
    assert reordered.status_code == 200
    assert [a["id"] for a in reordered.json()] == ids[::-1]
    listed = (await client.get(f"{BASE}/questions/{pending.id}")).json()["answers"]
    assert [a["id"] for a in listed] == ids[::-1]

    partial = await client.put(f"{url}/order", json={"ordered_ids": ids[:2]})
    assert partial.status_code == 422


# ── Exam date clearing ───────────────────────────────────────


async def test_exam_update_can_clear_date(client: AsyncClient):
    created = await client.post(
        f"{BASE}/exams", json={"partial_number": 1, "exam_date": "2025-05-01"}
    )
    exam_id = created.json()["id"]
    cleared = await client.put(f"{BASE}/exams/{exam_id}", json={"partial_number": 1})
    assert cleared.status_code == 200
    assert cleared.json()["exam_date"] is None
    assert (await client.get(f"{BASE}/exams/{exam_id}")).json()["exam"][
        "exam_date"
    ] is None


async def test_service_update_exam_none_date_still_means_unchanged(
    db_session: AsyncSession, default_subject
):
    from datetime import date

    from app.services.exam_service import ExamService

    service = ExamService(db_session)
    exam = await service.create_exam(partial_number=1, exam_date=date(2025, 5, 1))
    unchanged = await service.update_exam(exam.id, topic_tags="x")
    assert unchanged.exam_date == date(2025, 5, 1)
    cleared = await service.update_exam(exam.id, clear_exam_date=True)
    assert cleared.exam_date is None


# ── SPA static fallback ──────────────────────────────────────


@pytest.fixture
async def spa_client(tmp_path: Path):
    (tmp_path / "index.html").write_text("<html>spa</html>")
    (tmp_path / "app.js").write_text("console.log(1)")
    api = FastAPI()

    @api.get("/api/ping")
    async def ping() -> dict:
        return {"ok": True}

    api.mount("/", SPAStaticFiles(directory=tmp_path, html=True))
    async with AsyncClient(
        transport=ASGITransport(app=api), base_url="http://test"
    ) as c:
        yield c


async def test_spa_serves_existing_asset(spa_client: AsyncClient):
    response = await spa_client.get("/app.js")
    assert response.status_code == 200
    assert "console.log" in response.text


async def test_spa_missing_asset_is_404(spa_client: AsyncClient):
    assert (await spa_client.get("/missing.js")).status_code == 404
    assert (await spa_client.get("/assets/missing.css")).status_code == 404


async def test_spa_client_routes_fall_back_to_index(spa_client: AsyncClient):
    for path in ("/", "/practice", "/exams/1", "/practice/3/results"):
        response = await spa_client.get(path)
        assert response.status_code == 200, path
        assert "spa" in response.text


async def test_spa_leaves_api_alone(spa_client: AsyncClient):
    assert (await spa_client.get("/api/ping")).json() == {"ok": True}
    # Unknown API paths stay a real 404 instead of falling back to index.html.
    assert (await spa_client.get("/api/unknown")).status_code == 404


async def test_legacy_app_prefix_redirects_to_root(client: AsyncClient):
    response = await client.get("/app/practice/3?x=1")
    assert response.status_code == 308
    assert response.headers["location"] == "/practice/3?x=1"
    assert (await client.get("/app")).headers["location"] == "/"
