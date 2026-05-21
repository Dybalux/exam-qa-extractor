"""Analytics API routes."""

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_analytics_service
from app.schemas.analytics import (
    ExamCoverage,
    OverallStats,
    SessionHistoryItem,
    StudyProgress,
    TopicPerformanceItem,
    WeakArea,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter()


@router.get("/stats", response_model=OverallStats)
async def overall_stats(
    service: AnalyticsService = Depends(get_analytics_service),
) -> OverallStats:
    """Get system-wide statistics."""
    stats = await service.get_overall_stats()
    return OverallStats(**stats)


@router.get("/topic-performance", response_model=dict[str, TopicPerformanceItem])
async def topic_performance(
    user_session_id: str = Query(..., min_length=1),
    service: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    """Get accuracy breakdown by topic for a user."""
    return await service.get_topic_performance(user_session_id)


@router.get("/weak-areas", response_model=list[WeakArea])
async def weak_areas(
    user_session_id: str = Query(..., min_length=1),
    threshold_pct: float = Query(default=60.0, ge=0.0, le=100.0),
    service: AnalyticsService = Depends(get_analytics_service),
) -> list[WeakArea]:
    """Get topics where the user performs below the threshold."""
    areas = await service.get_weak_areas(user_session_id, threshold_pct)
    return [WeakArea(**a) for a in areas]


@router.get("/history", response_model=list[SessionHistoryItem])
async def session_history(
    user_session_id: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
    service: AnalyticsService = Depends(get_analytics_service),
) -> list[SessionHistoryItem]:
    """Get recent practice sessions for a user."""
    sessions = await service.get_session_history(user_session_id, limit)
    return [SessionHistoryItem(**s) for s in sessions]


@router.get("/progress", response_model=StudyProgress)
async def study_progress(
    service: AnalyticsService = Depends(get_analytics_service),
) -> StudyProgress:
    """Get content readiness broken down by partial and topic."""
    progress = await service.get_study_progress()
    return StudyProgress(**progress)


@router.get("/exams/{exam_id}/coverage", response_model=ExamCoverage)
async def exam_coverage(
    exam_id: int,
    service: AnalyticsService = Depends(get_analytics_service),
) -> ExamCoverage:
    """Get question coverage statistics for a specific exam."""
    coverage = await service.get_exam_coverage(exam_id)
    return ExamCoverage(**coverage)
