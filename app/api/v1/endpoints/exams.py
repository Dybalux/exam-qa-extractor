"""Exam API routes."""

import logging
from pathlib import Path
from typing import BinaryIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse

from app.core.exceptions import ConflictError, FileValidationError, NotFoundError, OCRProcessingError, StorageError, ValidationError
from app.dependencies import (
    get_answer_service,
    get_exam_service,
    get_ocr_service,
    get_question_service,
    get_storage_service,
)
from app.schemas.exam import ExamCreate, ExamResponse, ExamStats, ExamUpdate, TagsUpdate
from app.services.answer_service import AnswerService
from app.services.exam_service import ExamService
from app.services.ocr import BaseOCRProvider
from app.services.question_service import QuestionService
from app.services.storage_service import StorageService

router = APIRouter()
logger = logging.getLogger(__name__)


def _handle_domain_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, ValidationError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    raise exc


@router.post("/", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
async def create_exam(
    payload: ExamCreate,
    service: ExamService = Depends(get_exam_service),
) -> ExamResponse:
    """Create a new exam."""
    try:
        exam = await service.create_exam(
            partial_number=payload.partial_number,
            exam_date=payload.exam_date,
            topic_tags=payload.topic_tags,
        )
        return ExamResponse.model_validate(exam)
    except Exception as exc:
        _handle_domain_error(exc)


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
    try:
        exam = await service.get_exam(exam_id)
        return ExamResponse.model_validate(exam)
    except Exception as exc:
        _handle_domain_error(exc)


@router.patch("/{exam_id}", response_model=ExamResponse)
async def update_exam(
    exam_id: int,
    payload: ExamUpdate,
    service: ExamService = Depends(get_exam_service),
) -> ExamResponse:
    """Update exam metadata."""
    try:
        exam = await service.update_exam(
            exam_id=exam_id,
            exam_date=payload.exam_date,
            topic_tags=payload.topic_tags,
        )
        return ExamResponse.model_validate(exam)
    except Exception as exc:
        _handle_domain_error(exc)


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(
    exam_id: int,
    force: bool = False,
    service: ExamService = Depends(get_exam_service),
) -> None:
    """Delete an exam. Use ?force=true to delete even if questions exist."""
    try:
        await service.delete_exam(exam_id=exam_id, force=force)
    except Exception as exc:
        _handle_domain_error(exc)


@router.get("/{exam_id}/stats", response_model=ExamStats)
async def get_exam_stats(
    exam_id: int,
    service: ExamService = Depends(get_exam_service),
) -> ExamStats:
    """Get question statistics for an exam."""
    try:
        stats = await service.get_exam_stats(exam_id)
        return ExamStats(**stats)
    except Exception as exc:
        _handle_domain_error(exc)


@router.post("/{exam_id}/tags", response_model=ExamResponse)
async def add_tags(
    exam_id: int,
    payload: TagsUpdate,
    service: ExamService = Depends(get_exam_service),
) -> ExamResponse:
    """Add topic tags to an exam."""
    try:
        exam = await service.add_tags(exam_id, payload.tags)
        return ExamResponse.model_validate(exam)
    except Exception as exc:
        _handle_domain_error(exc)


@router.delete("/{exam_id}/tags", response_model=ExamResponse)
async def remove_tags(
    exam_id: int,
    payload: TagsUpdate,
    service: ExamService = Depends(get_exam_service),
) -> ExamResponse:
    """Remove topic tags from an exam."""
    try:
        exam = await service.remove_tags(exam_id, payload.tags)
        return ExamResponse.model_validate(exam)
    except Exception as exc:
        _handle_domain_error(exc)


@router.post("/{exam_id}/upload")
async def upload_exam_image(
    exam_id: int,
    file: UploadFile = File(...),
    language: str = "spa",
    exam_svc: ExamService = Depends(get_exam_service),
    storage_svc: StorageService = Depends(get_storage_service),
    ocr_svc: BaseOCRProvider = Depends(get_ocr_service),
    q_svc: QuestionService = Depends(get_question_service),
    ans_svc: AnswerService = Depends(get_answer_service),
) -> RedirectResponse:
    """Upload and process exam image with OCR.
    
    Saves the image, runs OCR, and creates questions from extracted text.
    Redirects to review queue or exam detail with flash message.
    """
    # Verify exam exists
    try:
        exam = await exam_svc.get_exam(exam_id)
    except NotFoundError:
        return RedirectResponse(url="/exams", status_code=302)
    
    # Validate file was provided
    if not file.filename:
        return RedirectResponse(
            url=f"/exams/{exam_id}/upload?message=No+se+proporcionó+archivo&type=error",
            status_code=303
        )
    
    try:
        # Read file data into BytesIO stream
        import io
        file_bytes = await file.read()
        file_stream = io.BytesIO(file_bytes)
        
        # Save file using storage service
        upload_result = await storage_svc.save_file(
            file_data=file_stream,
            original_filename=file.filename,
            exam_id=exam_id,
        )
        
        logger.info(f"File saved: {upload_result.storage_path}")
        
        # Run OCR on the saved file
        try:
            ocr_result = await ocr_svc.extract_from_path(upload_result.storage_path)
        except OCRProcessingError as ocr_err:
            # OCR failed but file was saved - redirect with warning
            logger.warning(f"OCR failed for {upload_result.storage_path}: {ocr_err}")
            return RedirectResponse(
                url=f"/exams/{exam_id}?message=Archivo+guardado+pero+OCR+falló:+{str(ocr_err)}&type=warning",
                status_code=303
            )
        
        # Create questions from OCR results
        questions_created = 0
        questions_needing_review = 0
        answers_created = 0
        
        for extracted_q in ocr_result.questions:
            try:
                question = await q_svc.create_question(
                    exam_id=exam_id,
                    question_text=extracted_q.text,
                    topic="other",  # Default topic, user should review
                    order_in_exam=extracted_q.order,
                    image_id=None,  # TODO: Create ExamImage record if needed
                    extracted_text=extracted_q.text,
                    confidence_score=extracted_q.confidence,
                )
                questions_created += 1
                
                if extracted_q.requires_review:
                    questions_needing_review += 1
                
                # Create answers if any exist (Tesseract returns empty list)
                for answer in extracted_q.answers:
                    try:
                        await ans_svc.create_answer(
                            question_id=question.id,
                            answer_text=answer.text,
                            answer_type=answer.answer_type,
                            explanation=answer.explanation,
                            display_order=answer.display_order,
                        )
                        answers_created += 1
                    except Exception as answer_err:
                        logger.error(f"Failed to create answer: {answer_err}")
                        await ans_svc.session.rollback()
                        continue
                        
            except Exception as e:
                logger.error(f"Failed to create question from OCR: {e}")
                await q_svc.session.rollback()
                continue
        
        # Build redirect message
        if questions_created > 0:
            message_parts = [f"Se crearon {questions_created} preguntas"]
            if answers_created > 0:
                message_parts.append(f"y {answers_created} respuestas")
            message = ". ".join(message_parts) + "."
            
            if questions_needing_review > 0:
                message += f" {questions_needing_review} necesitan revisión."
                redirect_url = f"/search/needs-review?exam_id={exam_id}&message={message.replace(' ', '+')}"
            else:
                redirect_url = f"/exams/{exam_id}?message={message.replace(' ', '+')}"
        else:
            message = "No se pudieron extraer preguntas del archivo."
            redirect_url = f"/exams/{exam_id}/upload?message={message.replace(' ', '+')}&type=warning"
        
        return RedirectResponse(url=redirect_url, status_code=303)
        
    except FileValidationError as e:
        logger.warning(f"File validation failed: {e}")
        return RedirectResponse(
            url=f"/exams/{exam_id}/upload?message=Archivo+inválido:+{str(e.message)}&type=error",
            status_code=303
        )
    except StorageError as e:
        logger.error(f"Storage error: {e}")
        return RedirectResponse(
            url=f"/exams/{exam_id}/upload?message=Error+al+guardar+archivo:+{str(e.message)}&type=error",
            status_code=303
        )
    except Exception as e:
        logger.error(f"Unexpected error processing upload: {e}")
        return RedirectResponse(
            url=f"/exams/{exam_id}/upload?message=Error+inesperado:+{str(e)}&type=error",
            status_code=303
        )
