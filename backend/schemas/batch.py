"""Pydantic v2 schemas for Batch Evaluation processing, status tracking, and export."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.consumers import TaskType
from backend.schemas.models import ModelID


class BatchPromptItem(BaseModel):
    """A single prompt entry in a batch evaluation dataset."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid4())[:8], description="Item identifier")
    prompt: str = Field(min_length=1, max_length=50000, description="Evaluation prompt")
    reference_output: str | None = Field(
        default=None, max_length=50000, description="Optional ground truth reference text"
    )


class BatchUploadRequest(BaseModel):
    """Payload to initiate a batch evaluation run across multiple prompts."""

    model_config = ConfigDict(str_strip_whitespace=True)

    items: list[BatchPromptItem] = Field(
        min_length=1, max_length=500, description="List of prompt items to evaluate"
    )
    models: list[ModelID] = Field(
        min_length=1, max_length=10, description="Models to benchmark on each prompt"
    )
    task_type: TaskType = Field(default=TaskType.QUESTION_ANSWERING, description="Task category")
    consumer_id: str | None = Field(default=None, description="Optional caller consumer ID")


class BatchItemResult(BaseModel):
    """Evaluation result for an individual prompt within a batch."""

    model_config = ConfigDict(str_strip_whitespace=True)

    item_id: str
    prompt: str
    reference_output: str | None = None
    run_id: str | None = None
    winner: str | None = None
    scores: list[dict] = Field(default_factory=list)
    status: str = Field(default="completed")
    error_message: str | None = None


class BatchStatusResponse(BaseModel):
    """Current processing progress and status of a batch evaluation job."""

    model_config = ConfigDict(from_attributes=True)

    batch_id: UUID
    status: str = Field(description="'pending', 'running', 'completed', or 'failed'")
    task_type: TaskType
    models: list[ModelID]
    total_items: int
    completed_items: int
    failed_items: int
    created_at: datetime
    completed_at: datetime | None = None


class BatchResultsResponse(BaseModel):
    """Full evaluation results for all processed items within a batch."""

    model_config = ConfigDict(from_attributes=True)

    batch_id: UUID
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    results: list[BatchItemResult]
