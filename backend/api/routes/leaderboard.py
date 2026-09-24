"""REST API endpoints for Model Leaderboard aggregations and automated recommendations."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.schemas.consumers import ScoringMetric, TaskType
from backend.schemas.leaderboard import (
    LeaderboardResponse,
    ModelRecommendation,
)
from backend.services.leaderboard import (
    get_leaderboard_data,
    get_model_recommendation,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Leaderboard"])


@router.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
    summary="Get aggregated model benchmark leaderboard with win rates and scores",
)
async def get_leaderboard(
    task_type: Annotated[TaskType | None, Query(description="Filter by task category")] = None,
    force_refresh: Annotated[
        bool, Query(description="Bypass Redis cache and recompute from DB")
    ] = False,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
) -> LeaderboardResponse:
    """Retrieve aggregated performance metrics for all benchmarked models.

    Results are cached in Redis for 5 minutes (TTL 300s). Pass force_refresh=true
    to trigger a fresh database aggregation.
    """
    return await get_leaderboard_data(
        task_type=task_type,
        session=session,
        force_refresh=force_refresh,
    )


@router.get(
    "/models/recommend",
    response_model=ModelRecommendation,
    summary="Get data-driven model recommendation for a specific task type and metric",
)
async def recommend_model(
    task_type: Annotated[
        TaskType, Query(description="Target task category for evaluation")
    ] = TaskType.QUESTION_ANSWERING,
    metric: Annotated[
        ScoringMetric,
        Query(description="Primary metric to optimize (bert_score, latency, cost, etc.)"),
    ] = ScoringMetric.BERT_SCORE,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
) -> ModelRecommendation:
    """Analyze empirical leaderboard statistics and recommend the highest-performing model."""
    return await get_model_recommendation(
        task_type=task_type,
        metric=metric,
        session=session,
    )
