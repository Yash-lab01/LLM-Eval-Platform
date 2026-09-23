"""Pydantic v2 schemas for Consumer Projects and Feature Configuration.

Defines the FeatureFlag enum, ScoringMetric enum, TaskType enum, and EvalConsumerConfig
which drives the Feature Middleware Layer (feature_router.py).
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.models import ModelID


class FeatureFlag(StrEnum):
    """Features activated dynamically per consumer project."""

    BASIC_SCORING = "basic_scoring"
    OBSERVABILITY = "observability"
    LLM_AS_JUDGE = "llm_as_judge"
    RAG_EVAL = "rag_eval"
    HALLUCINATION_DETECTION = "hallucination_detection"
    BATCH_EVAL = "batch_eval"
    REGRESSION_TESTING = "regression_testing"
    CUSTOM_RUBRIC = "custom_rubric"
    WEBHOOK_NOTIFICATIONS = "webhook_notifications"


class ScoringMetric(StrEnum):
    """Scoring metrics available across automated and AI-judge evaluators."""

    BERT_SCORE = "bert_score"
    ROUGE_L = "rouge_l"
    LATENCY = "latency"
    TOKEN_COUNT = "token_count"
    ESTIMATED_COST = "estimated_cost"
    HALLUCINATION_SCORE = "hallucination_score"
    LLM_JUDGE = "llm_judge"


class TaskType(StrEnum):
    """Canonical task classification taxonomy."""

    SUMMARIZATION = "summarization"
    QUESTION_ANSWERING = "question_answering"
    CODE_GENERATION = "code_generation"
    DATA_EXTRACTION = "data_extraction"
    CREATIVE_WRITING = "creative_writing"
    CLASSIFICATION = "classification"
    TRANSLATION = "translation"
    RAG_RESPONSE = "rag_response"
    COMMAND_GENERATION = "command_generation"


class EvalConsumerConfig(BaseModel):
    """Consumer configuration payload declaring active features and preferences."""

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    consumer_id: str = Field(
        min_length=3,
        max_length=100,
        pattern=r"^[a-z0-9-]+$",
        description="Unique kebab-case identifier for consumer project",
    )
    features: list[FeatureFlag] = Field(
        default_factory=list, description="Features to enable in the evaluation pipeline"
    )
    models: list[ModelID] = Field(
        min_length=1, max_length=10, description="List of models to benchmark"
    )
    task_type: TaskType = Field(
        default=TaskType.QUESTION_ANSWERING,
        description="Classification category for prompts and leaderboard tracking",
    )
    scoring_metrics: list[ScoringMetric] = Field(
        default_factory=lambda: [ScoringMetric.LATENCY, ScoringMetric.TOKEN_COUNT],
        description="Metrics to evaluate after model generation",
    )
    custom_rubric: dict[str, Any] | None = Field(
        default=None, description="Optional custom rubric criteria for task evaluation"
    )
    webhook_url: str | None = Field(
        default=None, description="Webhook endpoint for threshold alert notifications"
    )
    min_score_threshold: float | None = Field(
        default=None, description="Minimum score threshold triggering alert if breached"
    )


class ConsumerCreate(BaseModel):
    """Payload to register a new consumer project."""

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    name: str = Field(min_length=2, max_length=100, description="Friendly consumer project name")
    config: EvalConsumerConfig = Field(description="Initial consumer feature configuration")


class ConsumerResponse(BaseModel):
    """Consumer registration response including generated API key."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    api_key: str
    config: EvalConsumerConfig
    created_at: datetime
