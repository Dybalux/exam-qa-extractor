"""Database initialization utilities."""

import logging
from pathlib import Path
from typing import Any, cast

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.db.session import engine
from app.models.subject import Subject
from app.models.topic import Topic

logger = logging.getLogger(__name__)

# Path to the YAML seed file relative to this module.
_SEEDS_PATH = Path(__file__).resolve().parent / "seeds.yaml"


async def create_tables() -> None:
    """Create all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully")


async def drop_tables() -> None:
    """Drop all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.info("Database tables dropped successfully")


async def _load_seeds_config() -> dict:
    """Load and parse the seeds YAML file.

    Returns:
        Parsed YAML as a dict with 'subjects' key.

    Raises:
        FileNotFoundError: If the seeds file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
    """
    with open(_SEEDS_PATH, encoding="utf-8") as f:
        return cast(dict[str, Any], yaml.safe_load(f))


async def _seed_subjects_and_topics(session: AsyncSession) -> int:
    """Seed Subject and Topic records from seeds.yaml.

    Idempotent: skips subjects/topics that already exist (matched by slug).

    Returns:
        Total number of records created (subjects + topics).
    """
    config = await _load_seeds_config()
    created = 0

    for subj_def in config.get("subjects", []):
        name: str = subj_def["name"]
        slug: str = subj_def["slug"]

        # Check if subject already exists.
        existing = await session.execute(select(Subject).where(Subject.slug == slug))
        subject = existing.scalar_one_or_none()

        if subject is None:
            subject = Subject(name=name, slug=slug)
            session.add(subject)
            await session.flush()
            created += 1
            logger.info("Seeded subject: %s (slug=%s)", name, slug)

        # Seed topics for this subject.
        for topic_def in subj_def.get("topics", []):
            topic_name: str = topic_def["name"]
            topic_slug: str = topic_def["slug"]

            existing_topic = await session.execute(
                select(Topic).where(Topic.slug == topic_slug)
            )
            if existing_topic.scalar_one_or_none() is None:
                topic = Topic(
                    name=topic_name,
                    slug=topic_slug,
                    subject_id=subject.id,
                )
                session.add(topic)
                created += 1
                logger.info(
                    "Seeded topic: %s (slug=%s, subject=%s)",
                    topic_name,
                    topic_slug,
                    slug,
                )

    return created


async def seed_data(session: AsyncSession) -> None:
    """Seed database with initial data from seeds.yaml.

    Idempotent: only inserts records that do not already exist.
    """
    created = await _seed_subjects_and_topics(session)
    await session.commit()
    logger.info("Database seeded successfully (%d new records)", created)
