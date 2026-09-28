"""Pydantic v2 schemas for Regression Testing prompt suites and score delta reporting."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.consumers import TaskType
from backend.schemas.models import ModelID


class SuitePromptItem(BaseModel):
    """A prompt entry with optional reference output saved within a benchmark suite."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid4())[:8], description="Prompt identifier")
    prompt: str = Field(min_length=1, max_length=50000, description="Prompt text")
    reference_output: str | None = Field(
        default=None, max_length=50000, description="Expected ground truth reference output"
    )


class PromptSuiteCreate(BaseModel):
    """Payload to create and persist a new prompt benchmark suite."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=150, description="Suite display name")
    description: str | None = Field(default=None, max_length=1000, description="Suite description")
    task_type: TaskType = Field(default=TaskType.QUESTION_ANSWERING, description="Task category")
    prompts: list[SuitePromptItem] = Field(
        min_length=1, max_length=200, description="Collection of prompts in this suite"
    )


class PromptSuiteSchema(BaseModel):
    """Persisted prompt benchmark suite definition."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    task_type: TaskType
    prompts: list[SuitePromptItem]
    created_at: datetime


class SuiteRunRequest(BaseModel):
    """Request payload to execute a prompt suite against benchmarked models."""

    model_config = ConfigDict(str_strip_whitespace=True)

    models: list[ModelID] = Field(
        min_length=1, max_length=10, description="Target models for benchmark execution"
    )
    consumer_id: str | None = Field(default=None, description="Optional caller consumer ID")


class SuiteRunItemScore(BaseModel):
    """Scores recorded for a specific prompt and model during a suite execution run."""

    model_config = ConfigDict(from_attributes=True)

    prompt_id: str
    prompt: str
    model_id: ModelID
    bert_score_f1: float | None = None
    rouge_l: float | None = None
    llm_judge_score: float | None = None
    latency_ms: float = 0.0


class SuiteRunRecord(BaseModel):
    """Summary record of an executed prompt suite run."""

    model_config = ConfigDict(from_attributes=True)

    run_id: UUID
    suite_id: UUID
    models: list[ModelID]
    timestamp: datetime
    item_scores: list[SuiteRunItemScore]


class MetricDelta(BaseModel):
    """Comparison metric delta between baseline and candidate model runs."""

    baseline: float | None
    candidate: float | None
    delta: float = Field(description="candidate - baseline")


class PromptRegressionDelta(BaseModel):
    """Per-prompt performance regression or improvement analysis."""

    prompt_id: str
    prompt: str
    model_id: ModelID
    metrics: dict[str, MetricDelta]
    status: str = Field(description="'improved', 'degraded', or 'unchanged'")


class RegressionReport(BaseModel):
    """Comprehensive regression test report comparing two suite execution runs."""

    model_config = ConfigDict(from_attributes=True)

    suite_id: UUID
    baseline_run_id: UUID
    candidate_run_id: UUID
    total_prompts: int
    improved_count: int
    degraded_count: int
    unchanged_count: int
    net_quality_delta: float = Field(
        description="Average quality delta across all evaluated prompts"
    )
    deltas: list[PromptRegressionDelta]
