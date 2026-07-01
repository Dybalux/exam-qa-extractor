"""Subject and Topic management REST API endpoints.

Exposes CRUD endpoints for subjects and topics as dynamic database
entities, replacing the static TopicEnum.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.slug import slugify
from app.dependencies import get_db
from app.models.subject import Subject
from app.models.topic import Topic
from app.schemas.subject import SubjectCreate, SubjectResponse
from app.schemas.topic import TopicCreate, TopicResponse

router = APIRouter()


# ── Subjects ──────────────────────────────────────────────────


@router.get("/subjects", response_model=list[SubjectResponse], tags=["subjects"])
async def list_subjects(
    db: AsyncSession = Depends(get_db),
) -> list[SubjectResponse]:
    """List all subjects ordered by name."""
    result = await db.execute(select(Subject).order_by(Subject.name))
    subjects = result.scalars().all()
    return [SubjectResponse.model_validate(s) for s in subjects]


@router.get("/subjects/{subject_id}", response_model=SubjectResponse, tags=["subjects"])
async def get_subject(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
) -> SubjectResponse:
    """Get a single subject by ID."""
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalar_one_or_none()
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    return SubjectResponse.model_validate(subject)


@router.post(
    "/subjects", response_model=SubjectResponse, status_code=201, tags=["subjects"]
)
async def create_subject(
    payload: SubjectCreate,
    db: AsyncSession = Depends(get_db),
) -> SubjectResponse:
    """Create a new subject. Slug is auto-generated from name if not provided."""
    slug = payload.slug or slugify(payload.name)
    existing = await db.execute(select(Subject).where(Subject.slug == slug))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409, detail=f"Subject with slug '{slug}' already exists"
        )
    subject = Subject(name=payload.name.strip(), slug=slug)
    db.add(subject)
    await db.commit()
    await db.refresh(subject)
    return SubjectResponse.model_validate(subject)


# ── Topics ────────────────────────────────────────────────────


@router.get(
    "/subjects/{subject_id}/topics",
    response_model=list[TopicResponse],
    tags=["topics"],
)
async def list_topics_by_subject(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[TopicResponse]:
    """List all topics belonging to a subject, ordered by name."""
    result = await db.execute(
        select(Topic).where(Topic.subject_id == subject_id).order_by(Topic.name)
    )
    topics = result.scalars().all()
    return [TopicResponse.model_validate(t) for t in topics]


@router.get("/topics", response_model=list[TopicResponse], tags=["topics"])
async def list_all_topics(
    db: AsyncSession = Depends(get_db),
) -> list[TopicResponse]:
    """List all topics across all subjects, ordered by name."""
    result = await db.execute(select(Topic).order_by(Topic.name))
    topics = result.scalars().all()
    return [TopicResponse.model_validate(t) for t in topics]


@router.post("/topics", response_model=TopicResponse, status_code=201, tags=["topics"])
async def create_topic(
    payload: TopicCreate,
    db: AsyncSession = Depends(get_db),
) -> TopicResponse:
    """Create a new topic under a subject. Slug auto-generated if not provided."""
    # Verify subject exists
    subject_result = await db.execute(
        select(Subject).where(Subject.id == payload.subject_id)
    )
    if subject_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Subject not found")

    slug = payload.slug or slugify(payload.name)
    existing = await db.execute(select(Topic).where(Topic.slug == slug))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409, detail=f"Topic with slug '{slug}' already exists"
        )

    topic = Topic(
        name=payload.name.strip(),
        slug=slug,
        subject_id=payload.subject_id,
    )
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return TopicResponse.model_validate(topic)
