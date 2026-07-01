"""Integration tests for subject/topic REST API endpoints and page rendering.

Verifies that subject and topic CRUD endpoints work correctly and
that page routes render dynamic topics from the database instead of
hardcoded TopicEnum values.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam import Exam
from app.models.question import Question
from app.models.subject import Subject
from app.models.topic import Topic

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_subject_and_topics(session: AsyncSession) -> Subject:
    """Create a default Subject and a few Topics for testing."""
    subject = Subject(name="Sistemas Operativos", slug="sistemas-operativos")
    session.add(subject)
    await session.flush()

    topics_data = [
        ("processes", "Procesos"),
        ("memory", "Memoria"),
        ("scheduling", "Planificación"),
    ]
    for slug, name in topics_data:
        session.add(Topic(name=name, slug=slug, subject_id=subject.id))
    await session.flush()
    return subject


# ---------------------------------------------------------------------------
# Subject endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_subjects_empty(client: AsyncClient) -> None:
    """GET /api/v1/subjects returns empty list when no subjects exist."""
    response = await client.get("/api/v1/subjects")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_subjects_with_data(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /api/v1/subjects returns all subjects ordered by name."""
    await _seed_subject_and_topics(db_session)
    # Add a second subject to test ordering
    db_session.add(Subject(name="Redes", slug="redes"))
    await db_session.commit()

    response = await client.get("/api/v1/subjects")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Redes"
    assert data[1]["name"] == "Sistemas Operativos"


@pytest.mark.asyncio
async def test_get_subject_found(client: AsyncClient, db_session: AsyncSession) -> None:
    """GET /api/v1/subjects/{id} returns the subject."""
    subject = await _seed_subject_and_topics(db_session)
    await db_session.commit()

    response = await client.get(f"/api/v1/subjects/{subject.id}")
    assert response.status_code == 200
    assert response.json()["slug"] == "sistemas-operativos"
    assert response.json()["name"] == "Sistemas Operativos"


@pytest.mark.asyncio
async def test_get_subject_not_found(client: AsyncClient) -> None:
    """GET /api/v1/subjects/{id} returns 404 for unknown subject."""
    response = await client.get("/api/v1/subjects/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Subject not found"


@pytest.mark.asyncio
async def test_create_subject(client: AsyncClient, db_session: AsyncSession) -> None:
    """POST /api/v1/subjects creates a subject and returns it."""
    payload = {"name": "Bases de Datos"}
    response = await client.post("/api/v1/subjects", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Bases de Datos"
    assert data["slug"] == "bases-de-datos"
    assert data["id"] > 0

    # Verify persisted
    result = await db_session.execute(
        __import__("sqlalchemy").select(Subject).where(Subject.id == data["id"])
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_create_subject_with_custom_slug(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST /api/v1/subjects accepts a custom slug."""
    payload = {"name": "Bases de Datos", "slug": "bdd"}
    response = await client.post("/api/v1/subjects", json=payload)
    assert response.status_code == 201
    assert response.json()["slug"] == "bdd"


@pytest.mark.asyncio
async def test_create_subject_duplicate_slug(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST /api/v1/subjects rejects duplicate slug with 409."""
    await _seed_subject_and_topics(db_session)
    await db_session.commit()

    payload = {"name": "Sistemas Operativos V2", "slug": "sistemas-operativos"}
    response = await client.post("/api/v1/subjects", json=payload)
    assert response.status_code == 409
    assert "sistemas-operativos" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Topic endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_all_topics_empty(client: AsyncClient) -> None:
    """GET /api/v1/topics returns empty list when no topics exist."""
    response = await client.get("/api/v1/topics")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_all_topics(client: AsyncClient, db_session: AsyncSession) -> None:
    """GET /api/v1/topics returns all topics ordered by name."""
    await _seed_subject_and_topics(db_session)
    await db_session.commit()

    response = await client.get("/api/v1/topics")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    slugs = [t["slug"] for t in data]
    assert "memory" in slugs
    assert "processes" in slugs
    assert "scheduling" in slugs


@pytest.mark.asyncio
async def test_list_topics_by_subject(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /api/v1/subjects/{id}/topics returns only that subject's topics."""
    subject = await _seed_subject_and_topics(db_session)
    # Add a second subject with its own topics
    subject2 = Subject(name="Redes", slug="redes")
    db_session.add(subject2)
    await db_session.flush()
    db_session.add(Topic(name="TCP/IP", slug="tcp-ip", subject_id=subject2.id))
    await db_session.commit()

    response = await client.get(f"/api/v1/subjects/{subject.id}/topics")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    slugs = {t["slug"] for t in data}
    assert slugs == {"processes", "memory", "scheduling"}


@pytest.mark.asyncio
async def test_create_topic(client: AsyncClient, db_session: AsyncSession) -> None:
    """POST /api/v1/topics creates a topic under a subject."""
    subject = await _seed_subject_and_topics(db_session)
    await db_session.commit()

    payload = {
        "name": "Nuevo Tema",
        "subject_id": subject.id,
    }
    response = await client.post("/api/v1/topics", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Nuevo Tema"
    assert data["slug"] == "nuevo-tema"
    assert data["subject_id"] == subject.id


@pytest.mark.asyncio
async def test_create_topic_nonexistent_subject(client: AsyncClient) -> None:
    """POST /api/v1/topics with unknown subject_id returns 404."""
    payload = {"name": "Ghost Topic", "subject_id": 999}
    response = await client.post("/api/v1/topics", json=payload)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_topic_duplicate_slug(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST /api/v1/topics rejects duplicate slug with 409."""
    subject = await _seed_subject_and_topics(db_session)
    await db_session.commit()

    payload = {"name": "Memory", "subject_id": subject.id}
    response = await client.post("/api/v1/topics", json=payload)
    assert response.status_code == 409
    assert "memory" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Page rendering tests — dynamic topics in templates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_question_list_page_shows_dynamic_topics(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /questions renders topic filter from database topics."""
    subject = await _seed_subject_and_topics(db_session)
    exam = Exam(partial_number=1, subject_id=subject.id)
    db_session.add(exam)
    await db_session.flush()
    db_session.add(
        Question(
            exam_id=exam.id,
            question_text="Test question",
            topic_id=(
                await db_session.execute(
                    __import__("sqlalchemy").select(Topic).where(Topic.slug == "memory")
                )
            )
            .scalar_one()
            .id,
        )
    )
    await db_session.commit()

    response = await client.get("/questions")
    assert response.status_code == 200
    html = response.text

    # The template should show topic names (not raw slugs) in the filter
    assert "Memoria" in html
    assert "Procesos" in html
    assert "Planificación" in html

    # The template should use slugs as option values
    assert 'value="processes"' in html
    assert 'value="memory"' in html

    # The question badge should show the slug (topic property)
    assert "topic-memory" in html
    assert ">memory<" in html


@pytest.mark.asyncio
async def test_practice_start_page_shows_dynamic_topics(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /practice renders topic selector from database topics."""
    await _seed_subject_and_topics(db_session)
    await db_session.commit()

    response = await client.get("/practice")
    assert response.status_code == 200
    html = response.text

    assert "Procesos" in html
    assert "Memoria" in html
    assert "Planificación" in html
    assert 'value="processes"' in html


@pytest.mark.asyncio
async def test_manual_question_form_shows_dynamic_topics(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /exams/{id}/questions/new renders topic selector from DB topics."""
    subject = await _seed_subject_and_topics(db_session)
    exam = Exam(partial_number=1, subject_id=subject.id)
    db_session.add(exam)
    await db_session.commit()

    response = await client.get(f"/exams/{exam.id}/questions/new")
    assert response.status_code == 200
    html = response.text

    assert "Procesos" in html
    assert "Memoria" in html
    assert 'value="processes"' in html


@pytest.mark.asyncio
async def test_question_list_page_uses_topic_slug_in_badge(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Question badges display the topic slug (not TopicEnum display name)."""
    subject = await _seed_subject_and_topics(db_session)
    exam = Exam(partial_number=1, subject_id=subject.id)
    db_session.add(exam)
    await db_session.flush()
    # Query the memory topic
    from sqlalchemy import select as sa_select

    topic_result = await db_session.execute(
        sa_select(Topic).where(Topic.slug == "memory")
    )
    memory_topic = topic_result.scalar_one()
    db_session.add(
        Question(
            exam_id=exam.id,
            question_text="Virtual memory question",
            topic_id=memory_topic.id,
        )
    )
    await db_session.commit()

    response = await client.get("/questions")
    assert response.status_code == 200
    html = response.text

    # The badge CSS class uses topic-{slug}
    assert "topic-memory" in html
