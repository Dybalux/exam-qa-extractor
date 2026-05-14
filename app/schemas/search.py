"""Pydantic schemas for Search resources."""

from pydantic import BaseModel, Field

from app.schemas.question import QuestionResponse


class SearchQuery(BaseModel):
    """Search query parameters."""

    query: str = Field(..., min_length=1, max_length=200)
    topic: str | None = None
    exam_id: int | None = None
    partial_number: int | None = Field(None, ge=1, le=4)
    limit: int = Field(default=20, ge=1, le=100)


class SearchResults(BaseModel):
    """Search results container."""

    query: str
    total: int
    results: list[QuestionResponse]
