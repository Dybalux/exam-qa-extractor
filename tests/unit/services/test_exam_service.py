"""Unit tests for ExamService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.services.exam_service import ExamService


@pytest.mark.asyncio
async def test_create_exam_success(db_session: AsyncSession) -> None:
    """ExamService.create_exam returns an exam with the correct partial_number."""
    service = ExamService(db_session)
    exam = await service.create_exam(partial_number=1)
    assert exam.partial_number == 1
    assert exam.id is not None


@pytest.mark.asyncio
async def test_create_exam_invalid_partial_raises(db_session: AsyncSession) -> None:
    """partial_number outside 1-4 raises ValidationError."""
    service = ExamService(db_session)
    with pytest.raises(ValidationError):
        await service.create_exam(partial_number=5)


@pytest.mark.asyncio
async def test_get_exam_not_found_raises(db_session: AsyncSession) -> None:
    """get_exam with a non-existent ID raises NotFoundError."""
    service = ExamService(db_session)
    with pytest.raises(NotFoundError):
        await service.get_exam(99999)


@pytest.mark.asyncio
async def test_list_exams_empty(db_session: AsyncSession) -> None:
    """list_exams returns an empty sequence on a fresh DB."""
    service = ExamService(db_session)
    exams = await service.list_exams()
    assert list(exams) == []


@pytest.mark.asyncio
async def test_create_duplicate_exam_raises(db_session: AsyncSession) -> None:
    """Creating two exams with the same partial_number and date raises ConflictError."""
    from datetime import date

    service = ExamService(db_session)
    d = date(2024, 6, 1)
    await service.create_exam(partial_number=2, exam_date=d)
    with pytest.raises(ConflictError):
        await service.create_exam(partial_number=2, exam_date=d)
