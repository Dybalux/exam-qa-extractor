"""Question API routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.dependencies import get_question_service
from app.schemas.question import (
    BulkCreateRequest,
    BulkCreateResponse,
    OCRCorrection,
    QuestionCreate,
    QuestionResponse,
    QuestionUpdate,
)
from app.services.question_service import QuestionService

router = APIRouter()


def _handle_domain_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, ValidationError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    raise exc


@router.post("/", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
async def create_question(
    payload: QuestionCreate,
    service: QuestionService = Depends(get_question_service),
) -> QuestionResponse:
    """Create a single question."""
    try:
        q = await service.create_question(
            exam_id=payload.exam_id,
            question_text=payload.question_text,
            topic=payload.topic,
            order_in_exam=payload.order_in_exam,
            image_id=payload.image_id,
            extracted_text=payload.extracted_text,
            confidence_score=payload.confidence_score,
        )
        return QuestionResponse.model_validate(q)
    except Exception as exc:
        _handle_domain_error(exc)


@router.post("/bulk", response_model=BulkCreateResponse, status_code=status.HTTP_201_CREATED)
async def bulk_create_questions(
    payload: BulkCreateRequest,
    service: QuestionService = Depends(get_question_service),
) -> BulkCreateResponse:
    """Bulk create questions from OCR extraction results."""
    try:
        questions = await service.bulk_create_from_ocr(
            exam_id=payload.exam_id,
            questions_data=[q.model_dump() for q in payload.questions],
            image_id=payload.image_id,
        )
        return BulkCreateResponse(
            created=len(questions),
            questions=[QuestionResponse.model_validate(q) for q in questions],
        )
    except Exception as exc:
        _handle_domain_error(exc)


@router.get("/", response_model=list[QuestionResponse])
async def list_questions(
    exam_id: int | None = None,
    topic: str | None = None,
    is_corrected: bool | None = None,
    is_ready_for_practice: bool | None = None,
    service: QuestionService = Depends(get_question_service),
) -> list[QuestionResponse]:
    """List questions with optional filters."""
    questions = await service.list_questions(
        exam_id=exam_id,
        topic=topic,
        is_corrected=is_corrected,
        is_ready_for_practice=is_ready_for_practice,
    )
    return [QuestionResponse.model_validate(q) for q in questions]


@router.get("/{question_id}", response_model=QuestionResponse)
async def get_question(
    question_id: int,
    service: QuestionService = Depends(get_question_service),
) -> QuestionResponse:
    """Get a single question by ID."""
    try:
        q = await service.get_question(question_id)
        return QuestionResponse.model_validate(q)
    except Exception as exc:
        _handle_domain_error(exc)


@router.patch("/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: int,
    payload: QuestionUpdate,
    service: QuestionService = Depends(get_question_service),
) -> QuestionResponse:
    """Update question fields."""
    try:
        q = await service.update_question(question_id=question_id, **payload.model_dump(exclude_none=True))
        return QuestionResponse.model_validate(q)
    except Exception as exc:
        _handle_domain_error(exc)


@router.post("/{question_id}/correct", response_model=QuestionResponse)
async def correct_ocr_text(
    question_id: int,
    payload: OCRCorrection,
    service: QuestionService = Depends(get_question_service),
) -> QuestionResponse:
    """Submit a manual OCR correction for a question."""
    try:
        q = await service.correct_ocr_text(
            question_id=question_id,
            corrected_text=payload.corrected_text,
            notes=payload.notes,
        )
        return QuestionResponse.model_validate(q)
    except Exception as exc:
        _handle_domain_error(exc)


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: int,
    service: QuestionService = Depends(get_question_service),
) -> None:
    """Delete a question and its answers."""
    try:
        await service.delete_question(question_id)
    except Exception as exc:
        _handle_domain_error(exc)
