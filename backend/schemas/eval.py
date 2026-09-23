"""Pydantic v2 schemas for Evaluation Runs, Requests, Responses, and Scores.

Includes cross-field validation rules enforcing reference outputs for BERTScore.
"""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.schemas.consumers import EvalConsumerConfig, ScoringMetric, TaskType
from backend.schemas.models import ModelID


class PromptRunRequest(BaseModel):
    """Payload to trigger an evaluation run across multiple models."""

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    prompt: str = Field(min_length=1, description="Prompt text to send to models")
    task_type: TaskType = Field(default=TaskType.QUESTION_ANSWERING, description="Category of task")
    models: list[ModelID] = Field(
        min_length=1, max_length=10, description="Target models for benchmark"
    )
    consumer_id: str | None = Field(default=None, description="Optional caller consumer identifier")
    consumer_config: EvalConsumerConfig | None = Field(
        default=None, description="Optional custom feature config"
    )
    scoring_metrics: list[ScoringMetric] = Field(
        default_factory=lambda: [ScoringMetric.LATENCY, ScoringMetric.TOKEN_COUNT],
        description="Scoring metrics to execute",
    )
    reference_output: str | None = Field(
        default=None, description="Expected ground truth reference text"
    )

    @model_validator(mode="after")
    def validate_reference_requirements(self) -> "PromptRunRequest":
        """Enforce reference_output presence when semantic similarity metrics are requested."""
        metrics = self.scoring_metrics
        if self.consumer_config and self.consumer_config.scoring_metrics:
            metrics = list(set(metrics + self.consumer_config.scoring_metrics))

        if ScoringMetric.BERT_SCORE in metrics or ScoringMetric.ROUGE_L in metrics:
            if not self.reference_output or not self.reference_output.strip():
                raise ValueError(
                    "reference_output is required when BERT_SCORE or ROUGE_L is evaluated"
                )
        return self


class ModelResponseSchema(BaseModel):
    """Execution output and latency recorded for a single model generation."""

    model_config = ConfigDict(from_attributes=True)

    model_id: ModelID = Field(description="Model identifier")
    output: str = Field(description="Raw text output returned by the model")
    latency_ms: float = Field(ge=0.0, description="Latency in milliseconds")
    token_count: int = Field(ge=0, description="Total tokens consumed (input + output)")
    finish_reason: str = Field(default="stop", description="Generation completion reason")
    from_cache: bool = Field(default=False, description="Whether response came from Redis cache")
    attempt_number: int = Field(default=1, ge=1, description="Attempt number for retries")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Timestamp of generation"
    )


class EvalScoreSchema(BaseModel):
    """Scoring evaluation results for a single model's response."""

    model_config = ConfigDict(from_attributes=True)

    model_id: ModelID = Field(description="Evaluated model identifier")
    bert_score_f1: float | None = Field(
        default=None, ge=0.0, le=1.0, description="PyTorch BERTScore F1"
    )
    rouge_l: float | None = Field(
        default=None, ge=0.0, le=1.0, description="ROUGE-L similarity score"
    )
    latency_ms: float = Field(ge=0.0, description="Generation latency in milliseconds")
    token_count: int = Field(ge=0, description="Total tokens used")
    estimated_cost_usd: float = Field(
        default=0.0, ge=0.0, description="Estimated inference cost in USD"
    )
    hallucination_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="NLI hallucination risk"
    )
    llm_judge_score: float | None = Field(
        default=None, ge=0.0, le=10.0, description="G-eval LLM judge score"
    )


class EvalRunResult(BaseModel):
    """Complete summary of an evaluation run including all model outputs and scores."""

    model_config = ConfigDict(from_attributes=True)

    run_id: UUID
    prompt: str
    task_type: TaskType
    models: list[ModelID]
    status: str
    responses: list[ModelResponseSchema] = Field(default_factory=list)
    scores: list[EvalScoreSchema] = Field(default_factory=list)
    winner: ModelID | None = None
    created_at: datetime
    completed_at: datetime | None = None


class EvalRunSummary(BaseModel):
    """Concise representation of an evaluation run for lists and tables."""

    model_config = ConfigDict(from_attributes=True)

    run_id: UUID
    consumer_id: UUID | None = None
    task_type: TaskType
    models: list[ModelID]
    status: str
    created_at: datetime
    completed_at: datetime | None = None


class RunComparison(BaseModel):
    """Comparative analysis between two evaluation runs."""

    model_config = ConfigDict(from_attributes=True)

    run_id_a: UUID
    run_id_b: UUID
    score_deltas: dict[str, dict[str, float | None]] = Field(
        description="Nested mapping of model_id -> metric -> delta value"
    )
