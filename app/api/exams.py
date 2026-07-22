"""Exam API routes."""

import io
import logging
import re
import urllib.parse

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import RedirectResponse

from app.api._flash import redirect_with_flash
from app.core.exceptions import (
    FileValidationError,
    NotFoundError,
    StorageError,
)
from app.dependencies import (
    get_exam_service,
    get_ocr_service,
    get_question_service,
    get_storage_service,
)
from app.schemas.exam import ExamCreate, ExamResponse, ExamStats, ExamUpdate, TagsUpdate
from app.services.exam_service import ExamService
from app.services.ocr_service import OCRService
from app.services.question_service import QuestionService
from app.services.storage_service import StorageService

router = APIRouter()
logger = logging.getLogger(__name__)

_EXAMS_PATH_RE = re.compile(r"/exams/\d+")


def _validate_return_to(value: str, exam_id: int) -> str | None:
    """Validate and sanitise a ``return_to`` value for image upload redirects.

    Args:
        value: Raw ``return_to`` from the hidden form field.
        exam_id: The exam ID from the route parameter (trusted).

    Returns:
        A safe redirect URL with ``exam_id`` query param, or ``None`` if
        the value is rejected (open-redirect / unknown path / absolute URL).
    """
    parsed = urllib.parse.urlsplit(value)
    # Reject absolute and protocol-relative URLs.
    if parsed.netloc or parsed.scheme:
        return None
    path = parsed.path
    if path == "/search/needs-review":
        pass
    elif _EXAMS_PATH_RE.fullmatch(path):
        # Pin exam_id from the route param, not the user-supplied value.
        path = f"/exams/{exam_id}"
    else:
        return None
    # Preserve existing query params and add exam_id.
    qs = urllib.parse.parse_qs(parsed.query)
    qs["exam_id"] = [str(exam_id)]
    new_qs = urllib.parse.urlencode(qs, doseq=True)
    return f"{path}?{new_qs}" if new_qs else path


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


@router.post("/{exam_id}/upload")
async def upload_exam_image(
    exam_id: int,
    file: UploadFile = File(...),
    language: str = "spa",
    return_to: str | None = Form(None),
    exam_svc: ExamService = Depends(get_exam_service),
    storage_svc: StorageService = Depends(get_storage_service),
    ocr_svc: OCRService = Depends(get_ocr_service),
    q_svc: QuestionService = Depends(get_question_service),
) -> RedirectResponse:
    """Upload and process exam image with OCR.

    Saves the image, runs OCR, and creates questions from extracted text.
    Redirects to review queue or exam detail with flash message.
    """
    # Verify exam exists
    try:
        await exam_svc.get_exam(exam_id)
    except NotFoundError:
        return RedirectResponse(url="/exams", status_code=302)

    # Validate file was provided
    if not file.filename:
        return redirect_with_flash(
            f"/exams/{exam_id}/upload", "No se proporcionó archivo", "error"
        )

    try:
        # Save file first
        upload_result = await storage_svc.save_file(
            file_data=io.BytesIO(await file.read()),
            original_filename=file.filename,
            exam_id=exam_id,
        )

        try:
            # Process OCR
            ocr_result = await ocr_svc.extract_from_path(upload_result.storage_path)
        except Exception as ocr_err:
            # OCR failed but file was saved - redirect with warning
            logger.warning(f"OCR failed for {upload_result.storage_path}: {ocr_err}")
            return redirect_with_flash(
                f"/exams/{exam_id}",
                f"Archivo guardado pero OCR falló: {str(ocr_err)}",
                "warning",
            )

        # Create questions from OCR results
        questions_created = 0
        questions_needing_review = 0

        for extracted_q in ocr_result.questions:
            try:
                await q_svc.create_question(
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

            except Exception as e:
                logger.error(f"Failed to create question from OCR: {e}")
                continue

        # Determine redirect target (success path may be overridden by return_to).
        if questions_created > 0:
            if questions_needing_review > 0:
                default_url = f"/search/needs-review?exam_id={exam_id}"
                message = (
                    f"Se crearon {questions_created} preguntas. "
                    f"{questions_needing_review} necesitan revisión."
                )
            else:
                default_url = f"/exams/{exam_id}"
                message = f"Se crearon {questions_created} preguntas correctamente."

            # Apply return_to override if valid (success path only).
            if return_to:
                validated = _validate_return_to(return_to, exam_id)
                if validated:
                    return redirect_with_flash(validated, message)
            return redirect_with_flash(default_url, message)
        else:
            message = "No se pudieron extraer preguntas del archivo."
            return redirect_with_flash(f"/exams/{exam_id}/upload", message, "warning")

    except FileValidationError as e:
        logger.warning(f"File validation failed: {e}")
        return redirect_with_flash(
            f"/exams/{exam_id}/upload", f"Archivo inválido: {str(e.message)}", "error"
        )
    except StorageError as e:
        logger.error(f"Storage error: {e}")
        return redirect_with_flash(
            f"/exams/{exam_id}/upload",
            f"Error al guardar archivo: {str(e.message)}",
            "error",
        )
    except Exception as e:
        logger.error(f"Unexpected error processing upload: {e}")
        return redirect_with_flash(
            f"/exams/{exam_id}/upload", f"Error inesperado: {str(e)}", "error"
        )
