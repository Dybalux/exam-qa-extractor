"""Database initialization utilities."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.db.session import engine

logger = logging.getLogger(__name__)


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


async def seed_data(session: AsyncSession) -> None:
    """Seed database with initial data."""
    # Add any seed data here if needed
    logger.info("Database seeded successfully")
