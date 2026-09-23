"""Pydantic v2 schemas for Leaderboard Aggregations and Model Recommendations."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.consumers import ScoringMetric, TaskType
from backend.schemas.models import ModelID


class LeaderboardEntry(BaseModel):
    """Aggregated benchmark statistics for a model on a given task category."""

    model_config = ConfigDict(from_attributes=True)

    model_id: ModelID
    task_type: TaskType
    total_runs: int = Field(ge=0, description="Total number of evaluated runs")
    win_rate: float = Field(ge=0.0, le=100.0, description="Percentage of runs won against peers")
    avg_bert_score: float | None = Field(default=None, description="Average BERTScore F1")
    avg_rouge_l: float | None = Field(default=None, description="Average ROUGE-L score")
    avg_latency_ms: float = Field(ge=0.0, description="Average response latency in milliseconds")
    avg_token_count: float = Field(ge=0.0, description="Average token volume per response")
    total_estimated_cost_usd: float = Field(
        default=0.0, ge=0.0, description="Cumulative estimated cost"
    )


class LeaderboardResponse(BaseModel):
    """Collection of leaderboard entries with cache provenance."""

    model_config = ConfigDict(from_attributes=True)

    task_type: TaskType | None = Field(
        default=None, description="Filter task category if specified"
    )
    entries: list[LeaderboardEntry] = Field(default_factory=list)
    from_cache: bool = Field(default=False, description="Whether returned from Redis cache")
    cached_at: datetime | None = None


class ModelRecommendation(BaseModel):
    """Data-backed recommendation of the top model for a task type."""

    model_config = ConfigDict(from_attributes=True)

    task_type: TaskType
    recommended_model: ModelID
    metric: ScoringMetric
    score: float | None = None
    reason: str = Field(description="Data-driven rationale for recommendation")
