"""Pydantic schemas for Topic resources."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TopicCreate(BaseModel):
    """Payload to create a topic."""

    name: str = Field(..., min_length=1)
    slug: str | None = None
    subject_id: int


class TopicResponse(BaseModel):
    """Full topic representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: str
    name: str
    slug: str
    subject_id: int
    created_at: datetime
    updated_at: datetime
