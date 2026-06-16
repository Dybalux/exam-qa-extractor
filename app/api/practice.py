"""Practice session API routes."""

from fastapi import APIRouter, Depends

from app.dependencies import get_practice_service
from app.schemas.practice import (
    AnswerSubmission,
    ResponseRecord,
    SessionCreate,
    SessionResponse,
    SessionResults,
    SkipRequest,
)
from app.schemas.question import QuestionResponse
from app.services.practice_service import PracticeService

router = APIRouter()


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(
    payload: SessionCreate,
    service: PracticeService = Depends(get_practice_service),
) -> SessionResponse:
    """Start a new practice session."""
    session = await service.create_session(
        user_session_id=payload.user_session_id,
        mode=payload.mode,
        exam_id=payload.exam_id,
        filters=payload.filters,
        total_questions=payload.total_questions,
    )
    return SessionResponse.model_validate(session)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: int,
    service: PracticeService = Depends(get_practice_service),
) -> SessionResponse:
    """Get a practice session by ID."""
    session = await service.get_session(session_id)
    return SessionResponse.model_validate(session)


@router.get("/sessions/{session_id}/next", response_model=QuestionResponse | None)
async def get_next_question(
    session_id: int,
    service: PracticeService = Depends(get_practice_service),
) -> QuestionResponse | None:
    """Get the next unanswered question for this session. Returns null when session is complete."""
    question = await service.get_next_question(session_id)
    if question is None:
        return None
    return QuestionResponse.model_validate(question)


@router.post("/sessions/{session_id}/answer", response_model=ResponseRecord)
async def submit_answer(
    session_id: int,
    payload: AnswerSubmission,
    service: PracticeService = Depends(get_practice_service),
) -> ResponseRecord:
    """Submit an answer for the current question."""
    response = await service.submit_answer(
        session_id=session_id,
        question_id=payload.question_id,
        selected_answer_id=payload.selected_answer_id,
        time_spent_seconds=payload.time_spent_seconds,
        was_flagged=payload.was_flagged,
    )
    return ResponseRecord(
        question_id=response.question_id,
        selected_answer_id=response.selected_answer_id,
        is_correct=response.is_correct,
        time_spent_seconds=response.time_spent_seconds,
        was_flagged=response.was_flagged,
    )


@router.post("/sessions/{session_id}/skip", response_model=ResponseRecord)
async def skip_question(
    session_id: int,
    payload: SkipRequest,
    service: PracticeService = Depends(get_practice_service),
) -> ResponseRecord:
    """Skip the current question."""
    response = await service.skip_question(
        session_id=session_id,
        question_id=payload.question_id,
        time_spent_seconds=payload.time_spent_seconds,
    )
    return ResponseRecord(
        question_id=response.question_id,
        selected_answer_id=response.selected_answer_id,
        is_correct=response.is_correct,
        time_spent_seconds=response.time_spent_seconds,
        was_flagged=response.was_flagged,
    )


@router.post("/sessions/{session_id}/complete", response_model=SessionResponse)
async def complete_session(
    session_id: int,
    service: PracticeService = Depends(get_practice_service),
) -> SessionResponse:
    """Mark a practice session as completed."""
    session = await service.complete_session(session_id)
    return SessionResponse.model_validate(session)


@router.get("/sessions/{session_id}/results", response_model=SessionResults)
async def get_session_results(
    session_id: int,
    service: PracticeService = Depends(get_practice_service),
) -> SessionResults:
    """Get full results for a session."""
    results = await service.get_session_results(session_id)
    return SessionResults(**results)
