"""Pydantic v2 schemas for Prompt Library management and version tracking."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.consumers import TaskType


class PromptCreate(BaseModel):
    """Payload to create a new prompt template or test case."""

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    consumer_id: UUID | None = Field(default=None, description="Optional owning consumer UUID")
    content: str = Field(min_length=1, description="Prompt text or Jinja2 template")
    task_type: TaskType = Field(
        default=TaskType.QUESTION_ANSWERING, description="Target task category"
    )
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    parent_id: UUID | None = Field(
        default=None, description="Parent prompt UUID if versioned clone"
    )


class PromptUpdate(BaseModel):
    """Payload to update an existing prompt (creates a new version)."""

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    content: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None


class PromptVersionSchema(BaseModel):
    """Version snapshot of a prompt in history."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: int
    content: str
    created_at: datetime


class PromptResponse(BaseModel):
    """Full prompt model representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    consumer_id: UUID | None = None
    content: str
    task_type: TaskType
    version: int
    parent_id: UUID | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
