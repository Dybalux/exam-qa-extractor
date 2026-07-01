"""Tests for Subject, Topic models, relationship and slugify utility."""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.slug import slugify
from app.db.base import Base
from app.models.exam import Exam
from app.models.question import Question
from app.models.subject import Subject
from app.models.topic import Topic

UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a session bound to a fresh in-memory SQLite DB with all tables."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    async with factory() as s:
        yield s
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def test_slugify_utility() -> None:
    """Test the slugify utility function with various cases."""
    assert slugify("Sistemas Operativos 1") == "sistemas-operativos-1"
    assert slugify("Álgebra Lineal") == "algebra-lineal"
    assert slugify("  Trim/Leading/Spaces  ") == "trimleadingspaces"
    assert slugify("Special @# Char-acters!") == "special-char-acters"
    assert slugify("multiple---dashes") == "multiple-dashes"
    assert slugify("UPPERCASE to lowercase") == "uppercase-to-lowercase"


@pytest.mark.asyncio
async def test_subject_auto_generates_slug_and_uuid(session: AsyncSession) -> None:
    """Test that Subject auto-generates slug and uuid on creation."""
    subject = Subject(name="Sistemas Operativos")
    session.add(subject)
    await session.commit()
    await session.refresh(subject)

    assert subject.uuid is not None
    assert UUID4_RE.match(subject.uuid)
    assert subject.slug == "sistemas-operativos"


@pytest.mark.asyncio
async def test_topic_auto_generates_slug_and_uuid(session: AsyncSession) -> None:
    """Test that Topic auto-generates slug and uuid on creation."""
    subject = Subject(name="Sistemas Operativos")
    session.add(subject)
    await session.flush()

    topic = Topic(name="Procesos e Hilos", subject_id=subject.id)
    session.add(topic)
    await session.commit()
    await session.refresh(topic)

    assert topic.uuid is not None
    assert UUID4_RE.match(topic.uuid)
    assert topic.slug == "procesos-e-hilos"
    assert topic.subject_id == subject.id


@pytest.mark.asyncio
async def test_relationships_subject_topic_exam_question(session: AsyncSession) -> None:
    """Test the relationships among Subject, Topic, Exam, and Question."""
    subject = Subject(name="Sistemas Operativos")
    session.add(subject)
    await session.flush()

    topic = Topic(name="Administración de Memoria", subject_id=subject.id)
    session.add(topic)

    exam = Exam(partial_number=1, subject_id=subject.id)
    session.add(exam)
    await session.flush()

    question = Question(
        exam_id=exam.id,
        question_text="Explicar paginación bajo demanda.",
        topic_id=topic.id,
    )
    session.add(question)
    await session.commit()

    # Refresh and check relationships
    await session.refresh(subject)
    await session.refresh(topic)
    await session.refresh(exam)
    await session.refresh(question)

    assert topic in subject.topics
    assert exam in subject.exams
    assert question in topic.questions
    assert exam.subject == subject
    assert question.topic_relation == topic

    # Test property accessor
    assert question.topic == "administracion-de-memoria"
