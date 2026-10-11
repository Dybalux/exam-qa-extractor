"""Exam API routes."""

import logging

from fastapi import APIRouter, Depends

from app.dependencies import (
    get_exam_service,
)
from app.schemas.exam import ExamCreate, ExamResponse, ExamStats, ExamUpdate, TagsUpdate
from app.services.exam_service import ExamService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=ExamResponse, status_code=201)
async def create_exam(
    payload: ExamCreate,
    service: ExamService = Depends(get_exam_service),
) -> ExamResponse:
    """Create a new exam."""
    exam = await service.create_exam(
        partial_number=payload.partial_number,
        exam_date=payload.exam_date,
        topic_tags=payload.topic_tags,
        subject_id=payload.subject_id,
    )
    return ExamResponse.model_validate(exam)


@router.get("/", response_model=list[ExamResponse])
async def list_exams(
    partial_number: int | None = None,
    topic: str | None = None,
    service: ExamService = Depends(get_exam_service),
) -> list[ExamResponse]:
    """List exams with optional filters."""
    exams = await service.list_exams(partial_number=partial_number, topic=topic)
    return [ExamResponse.model_validate(e) for e in exams]


@router.get("/{exam_id}", response_model=ExamResponse)
async def get_exam(
    exam_id: int,
    service: ExamService = Depends(get_exam_service),
) -> ExamResponse:
    """Get a single exam by ID."""
    exam = await service.get_exam(exam_id)
    return ExamResponse.model_validate(exam)


@router.patch("/{exam_id}", response_model=ExamResponse)
async def update_exam(
    exam_id: int,
    payload: ExamUpdate,
    service: ExamService = Depends(get_exam_service),
) -> ExamResponse:
    """Update exam metadata."""
    exam = await service.update_exam(
        exam_id=exam_id,
        exam_date=payload.exam_date,
        topic_tags=payload.topic_tags,
    )
    return ExamResponse.model_validate(exam)


@router.delete("/{exam_id}", status_code=204)
async def delete_exam(
    exam_id: int,
    force: bool = False,
    service: ExamService = Depends(get_exam_service),
) -> None:
    """Delete an exam. Use ?force=true to delete even if questions exist."""
    await service.delete_exam(exam_id=exam_id, force=force)


@router.get("/{exam_id}/stats", response_model=ExamStats)
async def get_exam_stats(
    exam_id: int,
    service: ExamService = Depends(get_exam_service),
) -> ExamStats:
    """Get question statistics for an exam."""
    stats = await service.get_exam_stats(exam_id)
    return ExamStats(**stats)


@router.post("/{exam_id}/tags", response_model=ExamResponse)
async def add_tags(
    exam_id: int,
    payload: TagsUpdate,
    service: ExamService = Depends(get_exam_service),
) -> ExamResponse:
    """Add topic tags to an exam."""
    exam = await service.add_tags(exam_id, payload.tags)
    return ExamResponse.model_validate(exam)


@router.delete("/{exam_id}/tags", response_model=ExamResponse)
async def remove_tags(
    exam_id: int,
    payload: TagsUpdate,
    service: ExamService = Depends(get_exam_service),
) -> ExamResponse:
    """Remove topic tags from an exam."""
    exam = await service.remove_tags(exam_id, payload.tags)
    return ExamResponse.model_validate(exam)
