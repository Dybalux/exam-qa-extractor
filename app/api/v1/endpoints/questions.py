"""Question API routes."""

from fastapi import APIRouter, Depends

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


@router.post("/", response_model=QuestionResponse, status_code=201)
async def create_question(
    payload: QuestionCreate,
    service: QuestionService = Depends(get_question_service),
) -> QuestionResponse:
    """Create a single question."""
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


@router.post("/bulk", response_model=BulkCreateResponse, status_code=201)
async def bulk_create_questions(
    payload: BulkCreateRequest,
    service: QuestionService = Depends(get_question_service),
) -> BulkCreateResponse:
    """Bulk create questions from OCR extraction results."""
    questions = await service.bulk_create_from_ocr(
        exam_id=payload.exam_id,
        questions_data=[q.model_dump() for q in payload.questions],
        image_id=payload.image_id,
    )
    return BulkCreateResponse(
        created=len(questions),
        questions=[QuestionResponse.model_validate(q) for q in questions],
    )


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
    q = await service.get_question(question_id)
    return QuestionResponse.model_validate(q)


@router.patch("/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: int,
    payload: QuestionUpdate,
    service: QuestionService = Depends(get_question_service),
) -> QuestionResponse:
    """Update question fields."""
    q = await service.update_question(
        question_id=question_id, **payload.model_dump(exclude_none=True)
    )
    return QuestionResponse.model_validate(q)


@router.post("/{question_id}/correct", response_model=QuestionResponse)
async def correct_ocr_text(
    question_id: int,
    payload: OCRCorrection,
    service: QuestionService = Depends(get_question_service),
) -> QuestionResponse:
    """Submit a manual OCR correction for a question."""
    q = await service.correct_ocr_text(
        question_id=question_id,
        corrected_text=payload.corrected_text,
        notes=payload.notes,
    )
    return QuestionResponse.model_validate(q)


@router.delete("/{question_id}", status_code=204)
async def delete_question(
    question_id: int,
    service: QuestionService = Depends(get_question_service),
) -> None:
    """Delete a question and its answers."""
    await service.delete_question(question_id)
