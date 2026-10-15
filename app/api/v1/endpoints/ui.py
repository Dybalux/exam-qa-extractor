"""SPA-facing JSON endpoints: dashboard and the practice flow.

These back the SPA's dashboard and ``/practice*`` screens and delegate all
logic to the existing services. They are mounted under ``/api/v1/ui`` so they do not collide with the core REST
resources (``/api/v1/practice`` etc.).

The browser identity is the ``session_id`` cookie (see ``app.api.session``).
"""

import random

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.session import session_id_from_request
from app.core.constants import AnswerType, PracticeMode
from app.core.exceptions import ValidationError
from app.dependencies import (
    get_all_topics,
    get_analytics_service,
    get_answer_service,
    get_exam_service,
    get_practice_service,
)
from app.models.practice_session import PracticeSession
from app.schemas.ui import (
    AnswerFeedback,
    CurrentQuestionResponse,
    DashboardResponse,
    ExamPaperQuestion,
    ExamPaperResponse,
    PracticeAnswerOption,
    PracticeOptionsResponse,
    PracticeQuestion,
    PracticeResultsResponse,
    PracticeSessionCreate,
    SessionProgress,
    SkipQuestionRequest,
    SkipResponse,
    SubmitAnswerRequest,
)
from app.services.analytics_service import AnalyticsService
from app.services.answer_service import AnswerService
from app.services.exam_service import ExamService
from app.services.practice_service import PracticeService

router = APIRouter(prefix="/ui")

_COOKIE_MAX_AGE = 86400


def _progress(session: PracticeSession) -> SessionProgress:
    return SessionProgress(
        session_id=session.id,
        mode=session.mode,
        total_questions=session.total_questions,
        questions_answered=session.questions_answered,
        correct_count=session.correct_count,
        incorrect_count=session.incorrect_count,
        skipped_count=session.skipped_count,
        is_completed=session.is_completed,
    )


# ── Dashboard ────────────────────────────────────────────────


@router.get("/dashboard", response_model=DashboardResponse, tags=["ui"])
async def ui_dashboard(
    request: Request,
    response: Response,
    analytics: AnalyticsService = Depends(get_analytics_service),
    exam_svc: ExamService = Depends(get_exam_service),
) -> DashboardResponse:
    """Dashboard data: overall stats, readiness, exams and recent sessions."""
    session_id = session_id_from_request(request)
    stats = await analytics.get_overall_stats()
    progress = await analytics.get_study_progress()
    exams = await exam_svc.list_exams()
    history = await analytics.get_session_history(session_id, limit=5)
    response.set_cookie("session_id", session_id, max_age=_COOKIE_MAX_AGE)
    return DashboardResponse.model_validate(
        {"stats": stats, "progress": progress, "exams": exams, "history": history},
        from_attributes=True,
    )


# ── Practice ─────────────────────────────────────────────────


@router.get("/practice/options", response_model=PracticeOptionsResponse, tags=["ui"])
async def ui_practice_options(
    exam_svc: ExamService = Depends(get_exam_service),
    topics: list[dict[str, str]] = Depends(get_all_topics),
) -> PracticeOptionsResponse:
    """Modes, exams and topics for the start screen."""
    exams = await exam_svc.list_exams()
    return PracticeOptionsResponse.model_validate(
        {"modes": [m.value for m in PracticeMode], "exams": exams, "topics": topics},
        from_attributes=True,
    )


@router.post(
    "/practice/sessions",
    response_model=SessionProgress,
    status_code=201,
    tags=["ui"],
)
async def ui_practice_create(
    payload: PracticeSessionCreate,
    request: Request,
    response: Response,
    service: PracticeService = Depends(get_practice_service),
) -> SessionProgress:
    """Start a session. Domain errors (e.g. no questions) map to 422."""
    user_session_id = session_id_from_request(request)
    try:
        session = await service.create_session(
            user_session_id=user_session_id,
            mode=payload.mode,
            exam_id=payload.exam_id,
            filters={"topic": payload.topic} if payload.topic else None,
            total_questions=payload.total_questions,
        )
    except ValidationError as exc:
        # Only error_review gets the friendly message; other validation
        # failures (invalid mode, no questions for the filters) keep theirs.
        if payload.mode == PracticeMode.ERROR_REVIEW.value:
            raise HTTPException(
                status_code=422, detail="Todavía no tienes errores para revisar."
            ) from exc
        raise
    response.set_cookie("session_id", user_session_id, max_age=_COOKIE_MAX_AGE)
    return _progress(session)


@router.get(
    "/practice/sessions/{session_id}/current",
    response_model=CurrentQuestionResponse,
    tags=["ui"],
)
async def ui_practice_current(
    session_id: int,
    service: PracticeService = Depends(get_practice_service),
    a_svc: AnswerService = Depends(get_answer_service),
) -> CurrentQuestionResponse:
    """Next unanswered question; completes the session when none are left."""
    session = await service.get_session(session_id)
    if session.is_completed:
        return CurrentQuestionResponse(session=_progress(session), question=None)

    question = await service.get_next_question(session_id)
    if question is None:
        session = await service.complete_session(session_id)
        return CurrentQuestionResponse(session=_progress(session), question=None)

    answers = list(await a_svc.list_answers(question.id))
    random.shuffle(answers)  # so the correct answer isn't always first
    return CurrentQuestionResponse(
        session=_progress(session),
        question=PracticeQuestion(
            id=question.id,
            text=question.question_text,
            topic=question.topic,
            answers=[
                PracticeAnswerOption(id=a.id, text=a.answer_text) for a in answers
            ],
        ),
    )


@router.post(
    "/practice/sessions/{session_id}/answer",
    response_model=AnswerFeedback,
    tags=["ui"],
)
async def ui_practice_answer(
    session_id: int,
    payload: SubmitAnswerRequest,
    service: PracticeService = Depends(get_practice_service),
    a_svc: AnswerService = Depends(get_answer_service),
) -> AnswerFeedback:
    """Submit an answer and get the verdict, correct answer and explanation."""
    record = await service.submit_answer(
        session_id=session_id,
        question_id=payload.question_id,
        selected_answer_id=payload.selected_answer_id,
        time_spent_seconds=payload.time_spent_seconds,
    )
    answers = await a_svc.list_answers(payload.question_id)
    correct = next(
        (a for a in answers if a.answer_type == AnswerType.CORRECT.value), None
    )
    selected = next((a for a in answers if a.id == payload.selected_answer_id), None)

    explanation: str | None = None
    if not record.is_correct and selected and selected.explanation:
        selected_expl = selected.explanation.strip()
        if correct and correct.explanation:
            correct_expl = correct.explanation.strip()
            if selected_expl == correct_expl:
                explanation = selected_expl
            else:
                explanation = f"{selected_expl}\n\n{correct_expl}"
        else:
            explanation = selected_expl
    elif correct and correct.explanation:
        explanation = correct.explanation.strip()

    session = await service.get_session(session_id)
    return AnswerFeedback(
        is_correct=bool(record.is_correct),
        correct_answer_id=correct.id if correct else None,
        correct_answer_text=correct.answer_text if correct else None,
        explanation=explanation,
        session=_progress(session),
    )


@router.post(
    "/practice/sessions/{session_id}/skip",
    response_model=SkipResponse,
    tags=["ui"],
)
async def ui_practice_skip(
    session_id: int,
    payload: SkipQuestionRequest,
    service: PracticeService = Depends(get_practice_service),
) -> SkipResponse:
    """Skip the current question."""
    await service.skip_question(
        session_id=session_id,
        question_id=payload.question_id,
        time_spent_seconds=payload.time_spent_seconds,
    )
    session = await service.get_session(session_id)
    return SkipResponse(session=_progress(session))


@router.get(
    "/practice/sessions/{session_id}/results",
    response_model=PracticeResultsResponse,
    tags=["ui"],
)
async def ui_practice_results(
    session_id: int,
    service: PracticeService = Depends(get_practice_service),
) -> PracticeResultsResponse:
    """Per-question breakdown for a session."""
    results = await service.get_session_results(session_id)
    return PracticeResultsResponse.model_validate(results)


@router.post(
    "/practice/sessions/{session_id}/complete",
    response_model=SessionProgress,
    tags=["ui"],
)
async def ui_practice_complete(
    session_id: int,
    service: PracticeService = Depends(get_practice_service),
) -> SessionProgress:
    """Complete a practice session explicitly (e.g. on exam simulation timeout)."""
    session = await service.get_session(session_id)
    if not session.is_completed:
        session = await service.complete_session(session_id)
    return _progress(session)


@router.get(
    "/practice/sessions/{session_id}/paper",
    response_model=ExamPaperResponse,
    tags=["ui"],
)
async def ui_practice_exam_paper(
    session_id: int,
    service: PracticeService = Depends(get_practice_service),
) -> ExamPaperResponse:
    """Fetch all questions and user selections for an exam simulation."""
    data = await service.get_exam_paper(session_id)
    return ExamPaperResponse(
        session=_progress(data["session"]),
        questions=[
            ExamPaperQuestion(
                id=q["id"],
                text=q["text"],
                topic=q["topic"],
                answers=[
                    PracticeAnswerOption(id=a["id"], text=a["text"])
                    for a in q["answers"]
                ],
                selected_answer_id=q["selected_answer_id"],
            )
            for q in data["questions"]
        ],
    )
