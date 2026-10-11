"""API routers package."""

from fastapi import APIRouter

from app.api import (
    analytics,
    answers,
    exams,
    import_export,
    practice,
    questions,
    search,
)
from app.api.v1.endpoints.subjects import router as subjects_router
from app.api.v1.endpoints.ui import router as ui_router
from app.api.v1.endpoints.ui_content import router as ui_content_router

api_router = APIRouter()

api_router.include_router(exams.router, prefix="/exams", tags=["exams"])
api_router.include_router(questions.router, prefix="/questions", tags=["questions"])
api_router.include_router(answers.router, prefix="/answers", tags=["answers"])
api_router.include_router(practice.router, prefix="/practice", tags=["practice"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
# Empty prefix: the export/import endpoints live at /api/v1/{export,import},
# NOT nested under /exams. The /api/v1 part comes from app/main.py.
api_router.include_router(import_export.router, prefix="", tags=["import-export"])
api_router.include_router(subjects_router, prefix="", tags=["subjects", "topics"])
# SPA-facing JSON endpoints (dashboard + practice) under /api/v1/ui.
api_router.include_router(ui_router, prefix="", tags=["ui"])
api_router.include_router(ui_content_router, prefix="")
