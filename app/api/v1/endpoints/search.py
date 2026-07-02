"""Search API routes."""

from fastapi import APIRouter, Depends, Query

from app.core.constants import CONFIDENCE_MEDIUM
from app.dependencies import get_search_service
from app.schemas.question import QuestionResponse
from app.schemas.search import SearchResults
from app.services.search_service import SearchService

router = APIRouter()


@router.get("/", response_model=SearchResults)
async def search_questions(
    q: str = Query(..., min_length=1, description="Search term"),
    topic: str | None = None,
    exam_id: int | None = None,
    partial_number: int | None = Query(None, ge=1, le=4),
    limit: int = Query(default=20, ge=1, le=100),
    service: SearchService = Depends(get_search_service),
) -> SearchResults:
    """Full-text search across question and extracted text."""
    results = await service.search_questions(
        query=q,
        topic=topic,
        exam_id=exam_id,
        partial_number=partial_number,
        limit=limit,
    )
    return SearchResults(
        query=q,
        total=len(results),
        results=[QuestionResponse.model_validate(r) for r in results],
    )


@router.get("/needs-review", response_model=list[QuestionResponse])
async def questions_needing_review(
    exam_id: int | None = None,
    confidence_threshold: float = Query(default=CONFIDENCE_MEDIUM, ge=0.0, le=100.0),
    service: SearchService = Depends(get_search_service),
) -> list[QuestionResponse]:
    """Get questions that need manual OCR review (low confidence, not yet corrected)."""
    questions = await service.get_questions_needing_review(
        exam_id=exam_id,
        confidence_threshold=confidence_threshold,
    )
    return [QuestionResponse.model_validate(q) for q in questions]


@router.get("/no-answers", response_model=list[QuestionResponse])
async def questions_without_answers(
    exam_id: int | None = None,
    topic: str | None = None,
    service: SearchService = Depends(get_search_service),
) -> list[QuestionResponse]:
    """Get questions that have no correct answer yet (not ready for practice)."""
    questions = await service.get_questions_without_answers(
        exam_id=exam_id, topic=topic
    )
    return [QuestionResponse.model_validate(q) for q in questions]


@router.get("/by-topic/{topic}", response_model=list[QuestionResponse])
async def questions_by_topic(
    topic: str,
    limit: int = Query(default=50, ge=1, le=200),
    service: SearchService = Depends(get_search_service),
) -> list[QuestionResponse]:
    """Get all questions for a specific topic."""
    try:
        questions = await service.search_by_topic(topic=topic, limit=limit)
        return [QuestionResponse.model_validate(q) for q in questions]
    except ValueError as exc:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )


@router.get("/low-confidence", response_model=list[QuestionResponse])
async def low_confidence_questions(
    threshold: float = Query(default=CONFIDENCE_MEDIUM, ge=0.0, le=100.0),
    exam_id: int | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    service: SearchService = Depends(get_search_service),
) -> list[QuestionResponse]:
    """Get questions with low OCR confidence score."""
    questions = await service.get_low_confidence_questions(
        threshold=threshold,
        exam_id=exam_id,
        limit=limit,
    )
    return [QuestionResponse.model_validate(q) for q in questions]
