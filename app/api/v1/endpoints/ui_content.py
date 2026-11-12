"""SPA-facing JSON endpoints: exams, questions and analytics.

These back the SPA's ``/exams*``, ``/questions*`` (including answers and the
OCR review queue) and ``/analytics*`` screens and delegate all logic to the
existing services. They live under ``/api/v1/ui`` and read the ``session_id``
cookie (see ``app.api.session``).
"""

import io
import logging

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)

from app.api.session import session_id_from_request
from app.core.constants import AnswerType
from app.core.exceptions import (
    ConflictError,
    FileValidationError,
    NotFoundError,
    StorageError,
)
from app.dependencies import (
    get_all_topics,
    get_analytics_service,
    get_answer_service,
    get_exam_service,
    get_ocr_service,
    get_question_service,
    get_search_service,
    get_storage_service,
)
from app.models.answer import Answer
from app.models.exam import Exam
from app.schemas.ui import (
    AnalyticsResponse,
    AnswerInput,
    AnswerOrder,
    AnswerRow,
    CorrectionInput,
    ExamDetailResponse,
    ExamInput,
    ExamListItem,
    ManualQuestionCreate,
    QuestionCreated,
    QuestionDetailResponse,
    QuestionListResponse,
    QuestionRow,
    ReviewQueueResponse,
    TopicOption,
    UploadResult,
    WeakAreasResponse,
)
from app.services.analytics_service import AnalyticsService
from app.services.answer_service import AnswerService
from app.services.exam_service import ExamService
from app.services.ocr_service import OCRService
from app.services.question_service import QuestionService
from app.services.search_service import SearchService
from app.services.storage_service import StorageService

router = APIRouter(prefix="/ui", tags=["ui"])
logger = logging.getLogger(__name__)

_COOKIE_MAX_AGE = 86400


def _exam_item(exam: Exam) -> ExamListItem:
    return ExamListItem(
        id=exam.id,
        partial_number=exam.partial_number,
        exam_date=exam.exam_date,
        topic_tags=exam.topic_tags,
        question_count=len(exam.questions),
    )


def _tri_state(value: str | None) -> bool | None:
    return True if value == "true" else False if value == "false" else None


# ── Topics ───────────────────────────────────────────────────


@router.get("/topics", response_model=list[TopicOption])
async def ui_topics(
    topics: list[dict[str, str]] = Depends(get_all_topics),
) -> list[TopicOption]:
    """All topics, for form selectors."""
    return [TopicOption(**t) for t in topics]


# ── Exams ────────────────────────────────────────────────────


@router.get("/exams", response_model=list[ExamListItem])
async def ui_exam_list(
    partial_number: int | None = None,
    service: ExamService = Depends(get_exam_service),
) -> list[ExamListItem]:
    """Exams with question counts, optionally filtered by partial."""
    exams = await service.list_exams(partial_number=partial_number)
    return [_exam_item(e) for e in exams]


@router.post("/exams", response_model=ExamListItem, status_code=201)
async def ui_exam_create(
    payload: ExamInput,
    service: ExamService = Depends(get_exam_service),
) -> ExamListItem:
    exam = await service.create_exam(
        partial_number=payload.partial_number,
        exam_date=payload.exam_date,
        topic_tags=payload.topic_tags or None,
    )
    return _exam_item(exam)


@router.get("/exams/{exam_id}", response_model=ExamDetailResponse)
async def ui_exam_detail(
    exam_id: int,
    exam_svc: ExamService = Depends(get_exam_service),
    q_svc: QuestionService = Depends(get_question_service),
    analytics: AnalyticsService = Depends(get_analytics_service),
) -> ExamDetailResponse:
    """Exam, readiness coverage and its questions. 404 if the exam is missing."""
    exam = await exam_svc.get_exam(exam_id)
    questions = await q_svc.list_questions(exam_id=exam_id)
    coverage = await analytics.get_exam_coverage(exam_id)
    return ExamDetailResponse.model_validate(
        {"exam": _exam_item(exam), "coverage": coverage, "questions": questions},
        from_attributes=True,
    )


@router.put("/exams/{exam_id}", response_model=ExamListItem)
async def ui_exam_update(
    exam_id: int,
    payload: ExamInput,
    service: ExamService = Depends(get_exam_service),
) -> ExamListItem:
    exam = await service.update_exam(
        exam_id=exam_id,
        partial_number=payload.partial_number,
        exam_date=payload.exam_date,
        clear_exam_date=payload.exam_date is None,
        # The service treats None as "unchanged"; "" is how tags get cleared.
        topic_tags=(payload.topic_tags or "").strip(),
    )
    return _exam_item(exam)


@router.delete("/exams/{exam_id}", status_code=204)
async def ui_exam_delete(
    exam_id: int,
    force: bool = False,
    service: ExamService = Depends(get_exam_service),
) -> Response:
    """Delete an exam. 409 when it has questions and ``force`` is not set."""
    await service.delete_exam(exam_id, force=force)
    return Response(status_code=204)


@router.post("/exams/{exam_id}/upload", response_model=UploadResult)
async def ui_exam_upload(
    exam_id: int,
    file: UploadFile = File(...),
    language: str = Form("spa"),
    exam_svc: ExamService = Depends(get_exam_service),
    storage_svc: StorageService = Depends(get_storage_service),
    ocr_svc: OCRService = Depends(get_ocr_service),
    q_svc: QuestionService = Depends(get_question_service),
) -> UploadResult:
    """Save an exam image, run OCR and create questions from the result."""
    await exam_svc.get_exam(exam_id)
    if not file.filename:
        raise HTTPException(status_code=422, detail="No se proporcionó archivo")

    try:
        saved = await storage_svc.save_file(
            file_data=io.BytesIO(await file.read()),
            original_filename=file.filename,
            exam_id=exam_id,
        )
    except FileValidationError as exc:
        raise HTTPException(
            status_code=422, detail=f"Archivo inválido: {exc.message}"
        ) from exc
    except StorageError as exc:
        raise HTTPException(
            status_code=500, detail=f"Error al guardar archivo: {exc.message}"
        ) from exc

    try:
        ocr_result = await ocr_svc.extract_from_path(saved.storage_path)
    except Exception as exc:  # OCR engines raise many unrelated error types
        logger.warning("OCR failed for %s: %s", saved.storage_path, exc)
        raise HTTPException(
            status_code=422, detail=f"Archivo guardado pero OCR falló: {exc}"
        ) from exc

    created = 0
    needing_review = 0
    for extracted in ocr_result.questions:
        try:
            await q_svc.create_question(
                exam_id=exam_id,
                question_text=extracted.text,
                topic="other",  # default topic; the user reviews it afterwards
                order_in_exam=extracted.order,
                image_id=None,
                extracted_text=extracted.text,
                confidence_score=extracted.confidence,
            )
        except Exception as exc:  # keep going; one bad question must not abort all
            logger.error("Failed to create question from OCR: %s", exc)
            continue
        created += 1
        if extracted.requires_review:
            needing_review += 1

    if created == 0:
        raise HTTPException(
            status_code=422, detail="No se pudieron extraer preguntas del archivo."
        )
    if needing_review:
        message = (
            f"Se crearon {created} preguntas. {needing_review} necesitan revisión."
        )
    else:
        message = f"Se crearon {created} preguntas correctamente."
    return UploadResult(created=created, needing_review=needing_review, message=message)


@router.post(
    "/exams/{exam_id}/questions", response_model=QuestionCreated, status_code=201
)
async def ui_manual_question_create(
    exam_id: int,
    payload: ManualQuestionCreate,
    exam_svc: ExamService = Depends(get_exam_service),
    q_svc: QuestionService = Depends(get_question_service),
    a_svc: AnswerService = Depends(get_answer_service),
) -> QuestionCreated:
    """Create a manually typed question with its correct answer."""
    await exam_svc.get_exam(exam_id)
    question = await q_svc.create_question(
        exam_id=exam_id,
        question_text=payload.question_text.strip(),
        topic=payload.topic,
        order_in_exam=payload.order_in_exam,
        image_id=None,
        extracted_text=None,
        confidence_score=None,
    )
    await q_svc.update_question(
        question_id=question.id,
        is_corrected=True,
        correction_notes="Pregunta creada manualmente (sin OCR)",
    )
    await a_svc.create_answer(
        question_id=question.id,
        answer_text=payload.correct_answer_text.strip(),
        answer_type=AnswerType.CORRECT.value,
        explanation=(payload.explanation or "").strip() or None,
        display_order=0,
    )
    return QuestionCreated(id=question.id)


# ── Questions ────────────────────────────────────────────────


@router.get("/questions", response_model=QuestionListResponse)
async def ui_question_list(
    exam_id: int | None = None,
    topic: str | None = None,
    is_corrected: str | None = None,
    is_ready: str | None = None,
    service: QuestionService = Depends(get_question_service),
    exam_svc: ExamService = Depends(get_exam_service),
    topics: list[dict[str, str]] = Depends(get_all_topics),
) -> QuestionListResponse:
    """Questions filtered by exam, topic, correction and readiness."""
    questions = await service.list_questions(
        exam_id=exam_id,
        topic=topic or None,
        is_corrected=_tri_state(is_corrected),
        is_ready_for_practice=_tri_state(is_ready),
    )
    exams = await exam_svc.list_exams()
    return QuestionListResponse.model_validate(
        {"questions": questions, "exams": exams, "topics": topics},
        from_attributes=True,
    )


@router.get("/questions/review", response_model=ReviewQueueResponse)
async def ui_review_queue(
    exam_id: int | None = None,
    service: SearchService = Depends(get_search_service),
    exam_svc: ExamService = Depends(get_exam_service),
) -> ReviewQueueResponse:
    """Uncorrected questions with low or unknown OCR confidence."""
    questions = await service.get_questions_needing_review(exam_id=exam_id)
    exams = await exam_svc.list_exams()
    return ReviewQueueResponse.model_validate(
        {"questions": questions, "exams": exams}, from_attributes=True
    )


@router.get("/questions/{question_id}", response_model=QuestionDetailResponse)
async def ui_question_detail(
    question_id: int,
    q_svc: QuestionService = Depends(get_question_service),
    a_svc: AnswerService = Depends(get_answer_service),
) -> QuestionDetailResponse:
    question = await q_svc.get_question(question_id)
    answers = await a_svc.list_answers(question_id)
    return QuestionDetailResponse(
        question=QuestionRow.model_validate(question),
        extracted_text=question.extracted_text,
        correction_notes=question.correction_notes,
        answers=[AnswerRow.model_validate(a) for a in answers],
    )


@router.post("/questions/{question_id}/correct", response_model=QuestionRow)
async def ui_question_correct(
    question_id: int,
    payload: CorrectionInput,
    service: QuestionService = Depends(get_question_service),
) -> QuestionRow:
    """Replace the question text with a manual correction."""
    question = await service.correct_ocr_text(
        question_id=question_id,
        corrected_text=payload.corrected_text.strip(),
        notes=(payload.notes or "").strip() or None,
    )
    return QuestionRow.model_validate(question)


@router.delete("/questions/{question_id}", status_code=204)
async def ui_question_delete(
    question_id: int,
    service: QuestionService = Depends(get_question_service),
) -> Response:
    await service.delete_question(question_id)
    return Response(status_code=204)


# ── Answers ──────────────────────────────────────────────────

_ONE_CORRECT = "Solo puede haber una respuesta correcta por pregunta."


async def _own_answer(a_svc: AnswerService, question_id: int, answer_id: int) -> Answer:
    """Fetch an answer, 404 when it does not belong to ``question_id``."""
    answer = await a_svc.get_answer(answer_id)
    if answer.question_id != question_id:
        raise NotFoundError(f"Answer not found: {answer_id}")
    return answer


@router.post(
    "/questions/{question_id}/answers", response_model=AnswerRow, status_code=201
)
async def ui_answer_create(
    question_id: int,
    payload: AnswerInput,
    a_svc: AnswerService = Depends(get_answer_service),
) -> AnswerRow:
    """Add an answer at the end of the question's answer list."""
    existing = await a_svc.list_answers(question_id)
    try:
        answer = await a_svc.create_answer(
            question_id=question_id,
            answer_text=payload.answer_text,
            answer_type=payload.answer_type,
            explanation=(payload.explanation or "").strip() or None,
            is_common_misconception=payload.is_common_misconception,
            display_order=len(existing),
        )
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=_ONE_CORRECT) from exc
    return AnswerRow.model_validate(answer)


@router.put("/questions/{question_id}/answers/order", response_model=list[AnswerRow])
async def ui_answer_reorder(
    question_id: int,
    payload: AnswerOrder,
    a_svc: AnswerService = Depends(get_answer_service),
) -> list[AnswerRow]:
    """Persist a new display order (must list every answer of the question)."""
    answers = await a_svc.reorder_answers(question_id, payload.ordered_ids)
    return [AnswerRow.model_validate(a) for a in answers]


@router.put("/questions/{question_id}/answers/{answer_id}", response_model=AnswerRow)
async def ui_answer_update(
    question_id: int,
    answer_id: int,
    payload: AnswerInput,
    a_svc: AnswerService = Depends(get_answer_service),
) -> AnswerRow:
    await _own_answer(a_svc, question_id, answer_id)
    try:
        answer = await a_svc.update_answer(
            answer_id=answer_id,
            answer_text=payload.answer_text,
            answer_type=payload.answer_type,
            # "" (not None) is what clears an explanation in the service.
            explanation=(payload.explanation or "").strip(),
            is_common_misconception=payload.is_common_misconception,
        )
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=_ONE_CORRECT) from exc
    return AnswerRow.model_validate(answer)


@router.delete("/questions/{question_id}/answers/{answer_id}", status_code=204)
async def ui_answer_delete(
    question_id: int,
    answer_id: int,
    a_svc: AnswerService = Depends(get_answer_service),
) -> Response:
    await _own_answer(a_svc, question_id, answer_id)
    await a_svc.delete_answer(answer_id)
    return Response(status_code=204)


# ── Analytics ────────────────────────────────────────────────


@router.get("/analytics", response_model=AnalyticsResponse)
async def ui_analytics(
    request: Request,
    response: Response,
    service: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsResponse:
    """Overall stats, content readiness and the user's performance per topic."""
    session_id = session_id_from_request(request)
    stats = await service.get_overall_stats()
    progress = await service.get_study_progress()
    performance = await service.get_topic_performance(session_id)
    response.set_cookie("session_id", session_id, max_age=_COOKIE_MAX_AGE)
    return AnalyticsResponse.model_validate(
        {"stats": stats, "progress": progress, "performance": performance},
        from_attributes=True,
    )


@router.get("/analytics/weak-areas", response_model=WeakAreasResponse)
async def ui_weak_areas(
    request: Request,
    response: Response,
    threshold: float = 60.0,
    service: AnalyticsService = Depends(get_analytics_service),
) -> WeakAreasResponse:
    """Topics under ``threshold`` accuracy plus the latest sessions."""
    session_id = session_id_from_request(request)
    weak = await service.get_weak_areas(session_id, threshold_pct=threshold)
    history = await service.get_session_history(session_id, limit=10)
    response.set_cookie("session_id", session_id, max_age=_COOKIE_MAX_AGE)
    return WeakAreasResponse.model_validate(
        {"threshold": threshold, "weak_areas": weak, "history": history},
        from_attributes=True,
    )
