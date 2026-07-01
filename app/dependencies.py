"""FastAPI dependencies for injection."""

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.services.analytics_service import AnalyticsService
from app.services.answer_service import AnswerService
from app.services.exam_service import ExamService
from app.services.json_io_service import JsonIOService
from app.services.ocr_service import OCRService
from app.services.practice_service import PracticeService
from app.services.question_service import QuestionService
from app.services.search_service import SearchService
from app.services.storage_service import StorageService


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_exam_service(db: AsyncSession = Depends(get_db)) -> ExamService:
    """Dependency for ExamService."""
    return ExamService(db)


async def get_json_io_service(
    db: AsyncSession = Depends(get_db),
) -> JsonIOService:
    """Dependency for JsonIOService."""
    return JsonIOService(db)


async def get_question_service(db: AsyncSession = Depends(get_db)) -> QuestionService:
    """Dependency for QuestionService."""
    return QuestionService(db)


async def get_answer_service(db: AsyncSession = Depends(get_db)) -> AnswerService:
    """Dependency for AnswerService."""
    return AnswerService(db)


async def get_practice_service(db: AsyncSession = Depends(get_db)) -> PracticeService:
    """Dependency for PracticeService."""
    return PracticeService(db)


async def get_search_service(db: AsyncSession = Depends(get_db)) -> SearchService:
    """Dependency for SearchService."""
    return SearchService(db)


async def get_analytics_service(db: AsyncSession = Depends(get_db)) -> AnalyticsService:
    """Dependency for AnalyticsService."""
    return AnalyticsService(db)


async def get_all_topics(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, str]]:
    """Dependency that provides all topics as {slug, name} dicts.

    Used by page routes to render dynamic topic filters.
    """
    from sqlalchemy import select

    from app.models.topic import Topic

    result = await db.execute(select(Topic).order_by(Topic.name))
    return [{"slug": t.slug, "name": t.name} for t in result.scalars().all()]


async def get_ocr_service() -> OCRService:
    """Dependency for OCRService (stateless)."""
    return OCRService()


async def get_storage_service() -> StorageService:
    """Dependency for StorageService (stateless)."""
    return StorageService()
