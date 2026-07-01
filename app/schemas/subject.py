"""Pydantic schemas for Subject resources."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SubjectCreate(BaseModel):
    """Payload to create a subject."""

    name: str = Field(..., min_length=1)
    slug: str | None = None


class SubjectUpdate(BaseModel):
    """Payload to update a subject. At least one field must be provided."""

    name: str | None = Field(None, min_length=1)
    slug: str | None = None


class SubjectResponse(BaseModel):
    """Full subject representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: str
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime
