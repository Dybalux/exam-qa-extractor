"""API routers package."""

from fastapi import APIRouter

from app.api import import_export
from app.api.v1.endpoints.subjects import router as subjects_router
from app.api.v1.endpoints.ui import router as ui_router
from app.api.v1.endpoints.ui_content import router as ui_content_router

api_router = APIRouter()

# Empty prefix: the export/import endpoints live at /api/v1/{export,import},
# NOT nested under /exams. The /api/v1 part comes from app/main.py.
api_router.include_router(import_export.router, prefix="", tags=["import-export"])
api_router.include_router(subjects_router, prefix="", tags=["subjects", "topics"])
# SPA-facing JSON endpoints (dashboard + practice) under /api/v1/ui.
api_router.include_router(ui_router, prefix="", tags=["ui"])
api_router.include_router(ui_content_router, prefix="")
