"""Tests for the uuid column on Exam, Question, Answer models."""

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

from app.db.base import Base
from app.models.answer import Answer
from app.models.exam import Exam
from app.models.question import Question
from app.models.subject import Subject
from app.models.topic import Topic

UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


async def _seed_subject_and_topic(session: AsyncSession) -> tuple[int, int]:
    """Create a default subject and 'other' topic, return both IDs."""
    subject = Subject(name="Sistemas Operativos", slug="sistemas-operativos")
    session.add(subject)
    await session.flush()
    topic = Topic(name="Otros", slug="other", subject_id=subject.id)
    session.add(topic)
    await session.flush()
    return subject.id, topic.id


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


@pytest.mark.asyncio
async def test_exam_auto_generates_uuid(session: AsyncSession) -> None:
    subject_id, _ = await _seed_subject_and_topic(session)
    exam = Exam(partial_number=1, subject_id=subject_id)
    session.add(exam)
    await session.commit()
    await session.refresh(exam)
    assert exam.uuid is not None
    assert UUID4_RE.match(exam.uuid), f"uuid '{exam.uuid}' is not UUID4"


@pytest.mark.asyncio
async def test_two_exams_get_distinct_uuids(session: AsyncSession) -> None:
    subject_id, _ = await _seed_subject_and_topic(session)
    a, b = Exam(partial_number=1, subject_id=subject_id), Exam(
        partial_number=2, subject_id=subject_id
    )
    session.add_all([a, b])
    await session.commit()
    await session.refresh(a)
    await session.refresh(b)
    assert a.uuid != b.uuid


@pytest.mark.asyncio
async def test_caller_supplied_uuid_is_honored(session: AsyncSession) -> None:
    """Service code that pins identity (import flow) can pass an explicit uuid."""
    subject_id, _ = await _seed_subject_and_topic(session)
    pinned = "11111111-2222-4333-8444-555555555555"
    exam = Exam(uuid=pinned, partial_number=1, subject_id=subject_id)
    session.add(exam)
    await session.commit()
    await session.refresh(exam)
    assert exam.uuid == pinned


@pytest.mark.asyncio
async def test_question_auto_generates_uuid(session: AsyncSession) -> None:
    subject_id, topic_id = await _seed_subject_and_topic(session)
    exam = Exam(partial_number=1, subject_id=subject_id)
    session.add(exam)
    await session.flush()
    q1 = Question(exam_id=exam.id, question_text="Q1", topic_id=topic_id)
    q2 = Question(exam_id=exam.id, question_text="Q2", topic_id=topic_id)
    session.add_all([q1, q2])
    await session.commit()
    await session.refresh(q1)
    await session.refresh(q2)
    assert UUID4_RE.match(q1.uuid)
    assert UUID4_RE.match(q2.uuid)
    assert q1.uuid != q2.uuid


@pytest.mark.asyncio
async def test_answer_auto_generates_uuid(session: AsyncSession) -> None:
    subject_id, topic_id = await _seed_subject_and_topic(session)
    exam = Exam(partial_number=1, subject_id=subject_id)
    session.add(exam)
    await session.flush()
    q = Question(exam_id=exam.id, question_text="Q", topic_id=topic_id)
    session.add(q)
    await session.flush()
    a1 = Answer(question_id=q.id, answer_text="A", answer_type="correct")
    a2 = Answer(question_id=q.id, answer_text="B", answer_type="incorrect")
    session.add_all([a1, a2])
    await session.commit()
    await session.refresh(a1)
    await session.refresh(a2)
    assert UUID4_RE.match(a1.uuid)
    assert UUID4_RE.match(a2.uuid)
    assert a1.uuid != a2.uuid
