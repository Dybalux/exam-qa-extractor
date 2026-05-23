"""Page rendering router — returns TemplateResponse (HTML) views."""

import random
import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.exceptions import NotFoundError
from app.dependencies import (
    get_analytics_service,
    get_answer_service,
    get_exam_service,
    get_practice_service,
    get_question_service,
    get_search_service,
)
from app.services.analytics_service import AnalyticsService
from app.services.answer_service import AnswerService
from app.services.exam_service import ExamService
from app.services.practice_service import PracticeService
from app.services.question_service import QuestionService
from app.services.search_service import SearchService

templates = Jinja2Templates(directory="app/templates")
router = APIRouter()


def _ctx(
    request: Request,
    flash: dict | None = None,
    **kwargs: Any
) -> dict:
    """Build base template context with optional flash message."""
    context = {"request": request, **kwargs}
    if flash:
        context["flash"] = flash
    return context


def _get_flash_from_query(request: Request) -> dict | None:
    """Extract flash message from query params if present."""
    message = request.query_params.get("message")
    msg_type = request.query_params.get("type", "info")
    if message:
        return {"type": msg_type, "message": message}
    return None


def _redirect_with_flash(url: str, message: str, msg_type: str = "success") -> RedirectResponse:
    """Create redirect response with flash message in query params."""
    separator = "&" if "?" in url else "?"
    redirect_url = f"{url}{separator}message={message}&type={msg_type}"
    return RedirectResponse(url=redirect_url, status_code=303)


def _session_id(request: Request) -> str:
    """Get or create a browser session ID via cookie."""
    return request.cookies.get("session_id", str(uuid.uuid4()))


# ── Dashboard ────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    analytics: AnalyticsService = Depends(get_analytics_service),
    exam_svc: ExamService = Depends(get_exam_service),
) -> HTMLResponse:
    stats = await analytics.get_overall_stats()
    progress = await analytics.get_study_progress()
    exams = await exam_svc.list_exams()
    session_id = _session_id(request)
    history = await analytics.get_session_history(session_id, limit=5)
    flash = _get_flash_from_query(request)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=_ctx(
            request,
            flash=flash,
            page_title="Dashboard",
            stats=stats,
            progress=progress,
            exams=exams,
            history=history,
        )
    )


# ── Exams ────────────────────────────────────────────────────

@router.get("/exams", response_class=HTMLResponse)
async def exam_list(
    request: Request,
    partial_number: int | None = None,
    service: ExamService = Depends(get_exam_service),
) -> HTMLResponse:
    exams = await service.list_exams(partial_number=partial_number)
    flash = _get_flash_from_query(request)
    return templates.TemplateResponse(
        request=request,
        name="exams/list.html",
        context=_ctx(
            request, flash=flash, page_title="Exámenes", exams=exams, selected_partial=partial_number,
        )
    )


@router.get("/exams/new", response_class=HTMLResponse)
async def exam_new(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="exams/form.html", context=_ctx(
        request, page_title="Nuevo examen", exam=None,
    ))


@router.post("/exams/new")
async def exam_create(
    request: Request,
    service: ExamService = Depends(get_exam_service),
) -> RedirectResponse:
    form = await request.form()
    partial_number = int(form.get("partial_number", 1))
    exam_date_str = form.get("exam_date") or None
    topic_tags = form.get("topic_tags") or None
    exam_date = None
    if exam_date_str:
        from datetime import date
        exam_date = date.fromisoformat(exam_date_str)
    exam = await service.create_exam(partial_number=partial_number, exam_date=exam_date, topic_tags=topic_tags)
    return _redirect_with_flash(f"/exams/{exam.id}", "Examen creado correctamente")


@router.get("/exams/{exam_id}", response_class=HTMLResponse)
async def exam_detail(
    request: Request,
    exam_id: int,
    exam_svc: ExamService = Depends(get_exam_service),
    q_svc: QuestionService = Depends(get_question_service),
    analytics: AnalyticsService = Depends(get_analytics_service),
) -> HTMLResponse:
    try:
        exam = await exam_svc.get_exam(exam_id)
        questions = await q_svc.list_questions(exam_id=exam_id)
        coverage = await analytics.get_exam_coverage(exam_id)
    except NotFoundError:
        return RedirectResponse(url="/exams", status_code=302)
    flash = _get_flash_from_query(request)
    return templates.TemplateResponse(
        request=request,
        name="exams/detail.html",
        context=_ctx(
            request, flash=flash, page_title=f"Parcial {exam.partial_number}", exam=exam,
            questions=questions, coverage=coverage,
        )
    )


@router.get("/exams/{exam_id}/edit", response_class=HTMLResponse)
async def exam_edit(
    request: Request,
    exam_id: int,
    service: ExamService = Depends(get_exam_service),
) -> HTMLResponse:
    try:
        exam = await service.get_exam(exam_id)
    except NotFoundError:
        return RedirectResponse(url="/exams", status_code=302)
    return templates.TemplateResponse(request=request, name="exams/form.html", context=_ctx(
        request, page_title="Editar examen", exam=exam,
    ))


@router.post("/exams/{exam_id}/edit")
async def exam_edit_submit(
    request: Request,
    exam_id: int,
    service: ExamService = Depends(get_exam_service),
) -> RedirectResponse:
    form = await request.form()
    partial_number = int(form.get("partial_number", 1))
    exam_date_str = form.get("exam_date")
    exam_date = date.fromisoformat(exam_date_str) if exam_date_str else None
    topic_tags = form.get("topic_tags") or None
    try:
        await service.update_exam(
            exam_id=exam_id,
            partial_number=partial_number,
            exam_date=exam_date,
            topic_tags=topic_tags,
        )
    except NotFoundError:
        return RedirectResponse(url="/exams", status_code=302)
    return RedirectResponse(url=f"/exams/{exam_id}", status_code=303)


# ── Questions ────────────────────────────────────────────────

@router.get("/questions", response_class=HTMLResponse)
async def question_list(
    request: Request,
    exam_id: str | None = None,
    topic: str | None = None,
    is_corrected: str | None = None,
    is_ready: str | None = None,
    service: QuestionService = Depends(get_question_service),
    exam_svc: ExamService = Depends(get_exam_service),
) -> HTMLResponse:
    exam_id_val = int(exam_id) if exam_id and exam_id.strip() else None
    topic_val = topic if topic and topic.strip() else None
    is_corrected_val = True if is_corrected == "true" else False if is_corrected == "false" else None
    is_ready_val = True if is_ready == "true" else False if is_ready == "false" else None

    questions = await service.list_questions(
        exam_id=exam_id_val, topic=topic_val,
        is_corrected=is_corrected_val, is_ready_for_practice=is_ready_val,
    )
    exams = await exam_svc.list_exams()
    flash = _get_flash_from_query(request)
    return templates.TemplateResponse(
        request=request,
        name="questions/list.html",
        context=_ctx(
            request, flash=flash, page_title="Preguntas", questions=questions, exams=exams,
            filters={"exam_id": exam_id_val, "topic": topic_val, "is_corrected": is_corrected, "is_ready": is_ready},
        )
    )


@router.get("/questions/{question_id}", response_class=HTMLResponse)
async def question_detail(
    request: Request,
    question_id: int,
    q_svc: QuestionService = Depends(get_question_service),
    a_svc: AnswerService = Depends(get_answer_service),
) -> HTMLResponse:
    try:
        question = await q_svc.get_question(question_id)
        answers = await a_svc.list_answers(question_id)
    except NotFoundError:
        return RedirectResponse(url="/questions", status_code=302)
    flash = _get_flash_from_query(request)
    return templates.TemplateResponse(
        request=request,
        name="questions/detail.html",
        context=_ctx(
            request, flash=flash, page_title="Pregunta", question=question, answers=answers,
        )
    )


@router.get("/questions/{question_id}/correct", response_class=HTMLResponse)
async def question_correct(
    request: Request,
    question_id: int,
    service: QuestionService = Depends(get_question_service),
) -> HTMLResponse:
    try:
        question = await service.get_question(question_id)
    except NotFoundError:
        return RedirectResponse(url="/questions", status_code=302)
    return templates.TemplateResponse(request=request, name="questions/correct.html", context=_ctx(
        request, page_title="Corregir OCR", question=question,
    ))


@router.post("/questions/{question_id}/correct")
async def question_correct_submit(
    request: Request,
    question_id: int,
    service: QuestionService = Depends(get_question_service),
) -> RedirectResponse:
    form = await request.form()
    corrected_text = form.get("corrected_text", "")
    notes = form.get("notes") or None
    await service.correct_ocr_text(question_id=question_id, corrected_text=corrected_text, notes=notes)
    return _redirect_with_flash(f"/questions/{question_id}", "Corrección guardada correctamente")


@router.get("/exams/{exam_id}/upload", response_class=HTMLResponse)
async def bulk_upload_page(
    request: Request,
    exam_id: int,
    service: ExamService = Depends(get_exam_service),
) -> HTMLResponse:
    try:
        exam = await service.get_exam(exam_id)
    except NotFoundError:
        return RedirectResponse(url="/exams", status_code=302)
    flash = _get_flash_from_query(request)
    return templates.TemplateResponse(request=request, name="questions/bulk_upload.html", context=_ctx(
        request, page_title="Subir imágenes", exam=exam, flash=flash,
    ))


@router.get("/exams/{exam_id}/questions/new", response_class=HTMLResponse)
async def manual_question_form(
    request: Request,
    exam_id: int,
    exam_svc: ExamService = Depends(get_exam_service),
) -> HTMLResponse:
    """Show form to manually add a question with correct answer."""
    from app.core.constants import TopicEnum
    
    try:
        exam = await exam_svc.get_exam(exam_id)
    except NotFoundError:
        return RedirectResponse(url="/exams", status_code=302)
    
    return templates.TemplateResponse(
        request=request,
        name="questions/manual_form.html",
        context=_ctx(
            request,
            page_title="Nueva pregunta",
            exam=exam,
            topics=list(TopicEnum),
            form_data=None,
        )
    )


@router.post("/exams/{exam_id}/questions/new")
async def manual_question_create(
    request: Request,
    exam_id: int,
    exam_svc: ExamService = Depends(get_exam_service),
    q_svc: QuestionService = Depends(get_question_service),
    a_svc: AnswerService = Depends(get_answer_service),
) -> RedirectResponse:
    """Create question and correct answer from manual form."""
    from app.core.constants import TopicEnum
    
    try:
        exam = await exam_svc.get_exam(exam_id)
    except NotFoundError:
        return RedirectResponse(url="/exams", status_code=302)
    
    form = await request.form()
    
    # Extract form data
    question_text = form.get("question_text", "").strip()
    topic = form.get("topic", "")
    order_in_exam = form.get("order_in_exam")
    correct_answer_text = form.get("correct_answer_text", "").strip()
    explanation = form.get("explanation", "").strip() or None
    
    # Validation
    errors = []
    if not question_text:
        errors.append("El texto de la pregunta es obligatorio")
    if not topic:
        errors.append("Debes seleccionar un tema")
    if not correct_answer_text:
        errors.append("La respuesta correcta es obligatoria")
    
    if errors:
        # Re-render form with errors (simplified - just redirect back for now)
        # In a full implementation, you'd re-render with error messages
        return _redirect_with_flash(
            f"/exams/{exam_id}/questions/new",
            "Error: " + ", ".join(errors),
            msg_type="error"
        )
    
    try:
        # Create question (marked as manually created, not from OCR)
        question = await q_svc.create_question(
            exam_id=exam_id,
            question_text=question_text,
            topic=topic,
            order_in_exam=int(order_in_exam) if order_in_exam else None,
            image_id=None,  # No image since it's manual
            extracted_text=None,
            confidence_score=None,
        )
        
        # Mark as corrected (since it's manually entered, it's considered correct)
        await q_svc.update_question(
            question_id=question.id,
            is_corrected=True,
            correction_notes="Pregunta creada manualmente (sin OCR)"
        )
        
        # Create the correct answer
        await a_svc.create_answer(
            question_id=question.id,
            answer_text=correct_answer_text,
            answer_type="correct",
            explanation=explanation,
            display_order=0,
        )
        
        return _redirect_with_flash(
            f"/questions/{question.id}",
            "Pregunta y respuesta correcta guardadas. Ahora podés agregar respuestas incorrectas (distractores)."
        )
        
    except Exception as e:
        # Log error and redirect with message
        import logging
        logging.getLogger(__name__).error(f"Error creating manual question: {e}")
        return _redirect_with_flash(
            f"/exams/{exam_id}/questions/new",
            f"Error al guardar: {str(e)}",
            msg_type="error"
        )


# ── Answers ──────────────────────────────────────────────────

@router.get("/questions/{question_id}/answers/new", response_class=HTMLResponse)
async def answer_new(
    request: Request,
    question_id: int,
    q_svc: QuestionService = Depends(get_question_service),
) -> HTMLResponse:
    try:
        question = await q_svc.get_question(question_id)
    except NotFoundError:
        return RedirectResponse(url="/questions", status_code=302)
    return templates.TemplateResponse(request=request, name="answers/form.html", context=_ctx(
        request, page_title="Nueva respuesta", question=question, answer=None,
    ))


@router.post("/questions/{question_id}/answers/new")
async def answer_create(
    request: Request,
    question_id: int,
    service: AnswerService = Depends(get_answer_service),
) -> RedirectResponse:
    form = await request.form()
    await service.create_answer(
        question_id=question_id,
        answer_text=form.get("answer_text", ""),
        answer_type=form.get("answer_type", "incorrect"),
        explanation=form.get("explanation") or None,
        is_common_misconception=form.get("is_common_misconception") == "on",
    )
    return _redirect_with_flash(f"/questions/{question_id}", "Respuesta agregada correctamente")


@router.get("/questions/{question_id}/answers/{answer_id}/edit", response_class=HTMLResponse)
async def answer_edit(
    request: Request,
    question_id: int,
    answer_id: int,
    q_svc: QuestionService = Depends(get_question_service),
    a_svc: AnswerService = Depends(get_answer_service),
) -> HTMLResponse:
    try:
        question = await q_svc.get_question(question_id)
        answer = await a_svc.get_answer(answer_id)
    except NotFoundError:
        return RedirectResponse(url=f"/questions/{question_id}", status_code=302)
    return templates.TemplateResponse(request=request, name="answers/form.html", context=_ctx(
        request, page_title="Editar respuesta", question=question, answer=answer,
    ))


@router.post("/questions/{question_id}/answers/{answer_id}/edit")
async def answer_update(
    request: Request,
    question_id: int,
    answer_id: int,
    service: AnswerService = Depends(get_answer_service),
) -> RedirectResponse:
    form = await request.form()
    try:
        await service.update_answer(
            answer_id=answer_id,
            answer_text=form.get("answer_text", ""),
            answer_type=form.get("answer_type", "incorrect"),
            explanation=form.get("explanation") or None,
            is_common_misconception=form.get("is_common_misconception") == "on",
        )
        message = "Respuesta actualizada correctamente"
        type_ = "success"
    except Exception as e:
        message = f"Error al actualizar: {str(e)}"
        type_ = "error"
    return _redirect_with_flash(f"/questions/{question_id}", message, type_)


@router.get("/questions/{question_id}/answers/manage", response_class=HTMLResponse)
async def answer_manage(
    request: Request,
    question_id: int,
    q_svc: QuestionService = Depends(get_question_service),
    a_svc: AnswerService = Depends(get_answer_service),
) -> HTMLResponse:
    try:
        question = await q_svc.get_question(question_id)
        answers = await a_svc.list_answers(question_id)
    except NotFoundError:
        return RedirectResponse(url="/questions", status_code=302)
    return templates.TemplateResponse(request=request, name="answers/manage.html", context=_ctx(
        request, page_title="Gestionar respuestas", question=question, answers=answers,
    ))


# ── Practice ─────────────────────────────────────────────────

@router.get("/practice", response_class=HTMLResponse)
async def practice_start(
    request: Request,
    exam_svc: ExamService = Depends(get_exam_service),
) -> HTMLResponse:
    exams = await exam_svc.list_exams()
    flash = _get_flash_from_query(request)
    return templates.TemplateResponse(
        request=request,
        name="practice/start.html",
        context=_ctx(
            request, flash=flash, page_title="Iniciar práctica", exams=exams,
        )
    )


@router.post("/practice")
async def practice_create(
    request: Request,
    service: PracticeService = Depends(get_practice_service),
) -> RedirectResponse:
    form = await request.form()
    user_session_id = _session_id(request)
    exam_id = int(form["exam_id"]) if form.get("exam_id") else None
    topic = form.get("topic") or None
    session = await service.create_session(
        user_session_id=user_session_id,
        mode=form.get("mode", "random"),
        exam_id=exam_id,
        filters={"topic": topic} if topic else None,
        total_questions=int(form.get("total_questions", 10)),
    )
    response = RedirectResponse(url=f"/practice/{session.id}/play", status_code=303)
    response.set_cookie("session_id", user_session_id, max_age=86400)
    return response


@router.get("/practice/{session_id}/play", response_class=HTMLResponse)
async def practice_play(
    request: Request,
    session_id: int,
    service: PracticeService = Depends(get_practice_service),
    a_svc: AnswerService = Depends(get_answer_service),
) -> HTMLResponse:
    try:
        session = await service.get_session(session_id)
        if session.is_completed:
            return RedirectResponse(url=f"/practice/{session_id}/results", status_code=302)
        question = await service.get_next_question(session_id)
        if question is None:
            await service.complete_session(session_id)
            return RedirectResponse(url=f"/practice/{session_id}/results", status_code=302)
        answers = await a_svc.list_answers(question.id)
        random.shuffle(answers)  # Randomize answer order so correct answer isn't always first
    except NotFoundError:
        return RedirectResponse(url="/practice", status_code=302)
    return templates.TemplateResponse(request=request, name="practice/question.html", context=_ctx(
        request, page_title="Práctica", session=session, question=question, answers=answers,
    ))


@router.post("/practice/{session_id}/answer")
async def practice_submit(
    request: Request,
    session_id: int,
    service: PracticeService = Depends(get_practice_service),
) -> RedirectResponse:
    form = await request.form()
    question_id = int(form["question_id"])
    selected_answer_id = int(form["selected_answer_id"])
    time_spent = int(form.get("time_spent_seconds", 0))
    await service.submit_answer(
        session_id=session_id,
        question_id=question_id,
        selected_answer_id=selected_answer_id,
        time_spent_seconds=time_spent,
    )
    return RedirectResponse(url=f"/practice/{session_id}/play", status_code=303)


@router.post("/practice/{session_id}/skip")
async def practice_skip(
    request: Request,
    session_id: int,
    service: PracticeService = Depends(get_practice_service),
) -> RedirectResponse:
    form = await request.form()
    question_id = int(form["question_id"])
    time_spent = int(form.get("time_spent_seconds", 0))
    await service.skip_question(session_id=session_id, question_id=question_id, time_spent_seconds=time_spent)
    return RedirectResponse(url=f"/practice/{session_id}/play", status_code=303)


@router.get("/practice/{session_id}/results", response_class=HTMLResponse)
async def practice_results(
    request: Request,
    session_id: int,
    service: PracticeService = Depends(get_practice_service),
) -> HTMLResponse:
    try:
        session = await service.get_session(session_id)
        results = await service.get_session_results(session_id)
    except NotFoundError:
        return RedirectResponse(url="/practice", status_code=302)
    flash = _get_flash_from_query(request)
    return templates.TemplateResponse(
        request=request,
        name="practice/results.html",
        context=_ctx(
            request, flash=flash, page_title="Resultados", session=session, results=results,
        )
    )


# ── Search ───────────────────────────────────────────────────

@router.get("/search/needs-review", response_class=HTMLResponse)
async def needs_review(
    request: Request,
    exam_id: int | None = None,
    service: SearchService = Depends(get_search_service),
    exam_svc: ExamService = Depends(get_exam_service),
) -> HTMLResponse:
    questions = await service.get_questions_needing_review(exam_id=exam_id)
    exams = await exam_svc.list_exams()
    return templates.TemplateResponse(request=request, name="questions/review_queue.html", context=_ctx(
        request, page_title="Revisar OCR", questions=questions,
        exams=exams, selected_exam=exam_id,
    ))


# ── Analytics ────────────────────────────────────────────────

@router.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard(
    request: Request,
    service: AnalyticsService = Depends(get_analytics_service),
) -> HTMLResponse:
    stats = await service.get_overall_stats()
    progress = await service.get_study_progress()
    session_id = _session_id(request)
    performance = await service.get_topic_performance(session_id)
    flash = _get_flash_from_query(request)
    return templates.TemplateResponse(
        request=request,
        name="analytics/dashboard.html",
        context=_ctx(
            request, flash=flash, page_title="Estadísticas", stats=stats,
            progress=progress, performance=performance,
        )
    )


@router.get("/analytics/weak-areas", response_class=HTMLResponse)
async def analytics_weak_areas(
    request: Request,
    threshold: float = 60.0,
    service: AnalyticsService = Depends(get_analytics_service),
) -> HTMLResponse:
    session_id = _session_id(request)
    weak = await service.get_weak_areas(session_id, threshold_pct=threshold)
    history = await service.get_session_history(session_id, limit=10)
    flash = _get_flash_from_query(request)
    return templates.TemplateResponse(
        request=request,
        name="analytics/weak_areas.html",
        context=_ctx(
            request, flash=flash, page_title="Áreas débiles", weak_areas=weak,
            history=history, threshold=threshold,
        )
    )
