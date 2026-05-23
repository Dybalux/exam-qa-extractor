"""FastAPI dependencies for injection."""

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.services.analytics_service import AnalyticsService
from app.services.answer_service import AnswerService
from app.services.exam_service import ExamService
from app.services.ocr import get_ocr_provider, BaseOCRProvider
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


async def get_ocr_service() -> BaseOCRProvider:
    """Dependency for OCR provider (stateless)."""
    return get_ocr_provider()


async def get_storage_service() -> StorageService:
    """Dependency for StorageService (stateless)."""
    return StorageService()
