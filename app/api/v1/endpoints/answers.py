"""Answer API routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.dependencies import get_answer_service
from app.schemas.answer import AnswerCreate, AnswerResponse, AnswerUpdate, ReorderRequest
from app.services.answer_service import AnswerService

router = APIRouter()


def _handle_domain_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, ValidationError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    raise exc


@router.post("/", response_model=AnswerResponse, status_code=status.HTTP_201_CREATED)
async def create_answer(
    payload: AnswerCreate,
    service: AnswerService = Depends(get_answer_service),
) -> AnswerResponse:
    """Create a new answer for a question."""
    try:
        answer = await service.create_answer(
            question_id=payload.question_id,
            answer_text=payload.answer_text,
            answer_type=payload.answer_type,
            explanation=payload.explanation,
            is_common_misconception=payload.is_common_misconception,
            display_order=payload.display_order,
        )
        return AnswerResponse.model_validate(answer)
    except Exception as exc:
        _handle_domain_error(exc)


@router.get("/question/{question_id}", response_model=list[AnswerResponse])
async def list_answers(
    question_id: int,
    service: AnswerService = Depends(get_answer_service),
) -> list[AnswerResponse]:
    """List all answers for a question."""
    answers = await service.list_answers(question_id)
    return [AnswerResponse.model_validate(a) for a in answers]


@router.get("/{answer_id}", response_model=AnswerResponse)
async def get_answer(
    answer_id: int,
    service: AnswerService = Depends(get_answer_service),
) -> AnswerResponse:
    """Get a single answer by ID."""
    try:
        answer = await service.get_answer(answer_id)
        return AnswerResponse.model_validate(answer)
    except Exception as exc:
        _handle_domain_error(exc)


@router.patch("/{answer_id}", response_model=AnswerResponse)
async def update_answer(
    answer_id: int,
    payload: AnswerUpdate,
    service: AnswerService = Depends(get_answer_service),
) -> AnswerResponse:
    """Update an answer."""
    try:
        answer = await service.update_answer(
            answer_id=answer_id,
            **payload.model_dump(exclude_none=True),
        )
        return AnswerResponse.model_validate(answer)
    except Exception as exc:
        _handle_domain_error(exc)


@router.delete("/{answer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_answer(
    answer_id: int,
    service: AnswerService = Depends(get_answer_service),
) -> None:
    """Delete an answer."""
    try:
        await service.delete_answer(answer_id)
    except Exception as exc:
        _handle_domain_error(exc)


@router.post("/question/{question_id}/reorder", response_model=list[AnswerResponse])
async def reorder_answers(
    question_id: int,
    payload: ReorderRequest,
    service: AnswerService = Depends(get_answer_service),
) -> list[AnswerResponse]:
    """Reorder answers for a question."""
    try:
        answers = await service.reorder_answers(question_id, payload.ordered_ids)
        return [AnswerResponse.model_validate(a) for a in answers]
    except Exception as exc:
        _handle_domain_error(exc)
