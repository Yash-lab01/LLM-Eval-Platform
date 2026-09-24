"""Leaderboard & Recommendation Service.

Aggregates historical evaluation runs and computed scores from PostgreSQL.
Caches leaderboard outputs in Redis (DB 0) with a 5-minute (300s) TTL.
Computes model recommendations based on empirical benchmark metrics.
"""

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.redis_client import get_redis_client
from backend.models.eval import EvalRun, EvalScoreORM
from backend.schemas.consumers import ScoringMetric, TaskType
from backend.schemas.leaderboard import (
    LeaderboardEntry,
    LeaderboardResponse,
    ModelRecommendation,
)
from backend.schemas.models import ModelID

logger = logging.getLogger(__name__)

LEADERBOARD_CACHE_PREFIX = "cache:leaderboard"
LEADERBOARD_CACHE_TTL_SECONDS = 300  # 5 minutes


def _get_cache_key(task_type: TaskType | str | None) -> str:
    """Format Redis key for leaderboard query caching."""
    type_str = task_type.value if isinstance(task_type, TaskType) else (task_type or "all")
    return f"{LEADERBOARD_CACHE_PREFIX}:{type_str}"


async def invalidate_leaderboard_cache(task_type: TaskType | str | None = None) -> None:
    """Invalidate Redis leaderboard cache for a specific task type or all categories."""
    try:
        redis_client = get_redis_client()
        keys_to_delete = [_get_cache_key(None)]  # Invalidate 'all'
        if task_type:
            keys_to_delete.append(_get_cache_key(task_type))

        await redis_client.delete(*keys_to_delete)
        logger.debug(f"Invalidated leaderboard cache keys: {keys_to_delete}")
    except Exception as exc:
        logger.warning(f"Failed to invalidate leaderboard cache: {exc}")


async def get_leaderboard_data(
    task_type: TaskType | None,
    session: AsyncSession,
    force_refresh: bool = False,
) -> LeaderboardResponse:
    """Retrieve aggregated leaderboard statistics from Redis cache or calculate from DB."""
    cache_key = _get_cache_key(task_type)
    redis_client = None

    try:
        redis_client = get_redis_client()
    except Exception as exc:
        logger.debug(f"Redis client unavailable in leaderboard service: {exc}")

    # 1. Attempt cache lookup if not forcing refresh
    if not force_refresh and redis_client:
        try:
            cached_bytes = await redis_client.get(cache_key)
            if cached_bytes:
                data = json.loads(cached_bytes)
                cached_at = (
                    datetime.fromisoformat(data["cached_at"]) if data.get("cached_at") else None
                )
                entries = [LeaderboardEntry(**entry) for entry in data.get("entries", [])]
                return LeaderboardResponse(
                    task_type=task_type,
                    entries=entries,
                    from_cache=True,
                    cached_at=cached_at,
                )
        except Exception as exc:
            logger.warning(f"Error reading leaderboard from cache: {exc}")

    # 2. Database Aggregation Query
    task_filter = [EvalRun.task_type == task_type.value] if task_type else []

    # Window query to rank models per run to calculate win counts
    rank_window = (
        func.row_number()
        .over(
            partition_by=EvalScoreORM.run_id,
            order_by=(
                func.coalesce(EvalScoreORM.bert_score_f1, 0.0).desc(),
                func.coalesce(EvalScoreORM.rouge_l, 0.0).desc(),
                EvalScoreORM.latency_ms.asc(),
            ),
        )
        .label("rank")
    )

    rank_subquery = (
        select(
            EvalScoreORM.model_id,
            EvalScoreORM.run_id,
            rank_window,
        )
        .join(EvalRun, EvalScoreORM.run_id == EvalRun.id)
        .where(*task_filter)
        .subquery()
    )

    wins_query = (
        select(
            rank_subquery.c.model_id,
            func.count().label("win_count"),
        )
        .where(rank_subquery.c.rank == 1)
        .group_by(rank_subquery.c.model_id)
    )

    wins_result = await session.execute(wins_query)
    wins_by_model: dict[str, int] = {row[0]: row[1] for row in wins_result.all()}

    # Main aggregation query across scores and runs
    stats_query = (
        select(
            EvalScoreORM.model_id,
            func.count(EvalScoreORM.id).label("total_runs"),
            func.avg(EvalScoreORM.bert_score_f1).label("avg_bert"),
            func.avg(EvalScoreORM.rouge_l).label("avg_rouge"),
            func.avg(EvalScoreORM.latency_ms).label("avg_latency"),
            func.avg(EvalScoreORM.token_count).label("avg_tokens"),
            func.sum(EvalScoreORM.estimated_cost_usd).label("total_cost"),
        )
        .join(EvalRun, EvalScoreORM.run_id == EvalRun.id)
        .where(*task_filter)
        .group_by(EvalScoreORM.model_id)
    )

    stats_result = await session.execute(stats_query)
    rows = stats_result.all()

    entries: list[LeaderboardEntry] = []
    resolved_task_type = task_type or TaskType.QUESTION_ANSWERING

    for row in rows:
        model_str = row[0]
        total = row[1] or 0
        avg_bert = float(row[2]) if row[2] is not None else None
        avg_rouge = float(row[3]) if row[3] is not None else None
        avg_latency = float(row[4]) if row[4] is not None else 0.0
        avg_tokens = float(row[5]) if row[5] is not None else 0.0
        total_cost = float(row[6]) if row[6] is not None else 0.0

        wins = wins_by_model.get(model_str, 0)
        win_rate = round((wins / total * 100.0), 1) if total > 0 else 0.0

        try:
            model_id_enum = ModelID(model_str)
        except ValueError:
            # Skip unmapped models
            continue

        entries.append(
            LeaderboardEntry(
                model_id=model_id_enum,
                task_type=resolved_task_type,
                total_runs=total,
                win_rate=win_rate,
                avg_bert_score=round(avg_bert, 4) if avg_bert is not None else None,
                avg_rouge_l=round(avg_rouge, 4) if avg_rouge is not None else None,
                avg_latency_ms=round(avg_latency, 2),
                avg_token_count=round(avg_tokens, 1),
                total_estimated_cost_usd=round(total_cost, 6),
            )
        )

    # Sort entries by win rate descending, then latency ascending
    entries.sort(key=lambda e: (e.win_rate, -e.avg_latency_ms), reverse=True)

    now = datetime.now(UTC)
    response = LeaderboardResponse(
        task_type=task_type,
        entries=entries,
        from_cache=False,
        cached_at=now,
    )

    # 3. Cache results in Redis
    if redis_client:
        try:
            cache_payload = response.model_dump(mode="json")
            await redis_client.set(
                cache_key,
                json.dumps(cache_payload),
                ex=LEADERBOARD_CACHE_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning(f"Failed to cache leaderboard in Redis: {exc}")

    return response


async def get_model_recommendation(
    task_type: TaskType,
    metric: ScoringMetric,
    session: AsyncSession,
) -> ModelRecommendation:
    """Recommend the optimal model for a task type based on empirical leaderboard metrics."""
    leaderboard = await get_leaderboard_data(task_type=task_type, session=session)

    if not leaderboard.entries:
        # Default recommendation when no benchmark data exists yet
        default_model = ModelID.GEMINI_3_5_FLASH
        return ModelRecommendation(
            task_type=task_type,
            recommended_model=default_model,
            metric=metric,
            score=None,
            reason=(
                f"No benchmark runs recorded for task type '{task_type.value}'. "
                f"Defaulting to {default_model.value} for high baseline efficiency."
            ),
        )

    # Selection logic based on requested metric
    entries = list(leaderboard.entries)
    chosen_entry: LeaderboardEntry
    score: float | None = None
    reason: str

    if metric == ScoringMetric.BERT_SCORE:
        # Filter entries with bert scores
        with_bert = [e for e in entries if e.avg_bert_score is not None]
        if with_bert:
            chosen_entry = max(with_bert, key=lambda e: e.avg_bert_score or 0.0)
            score = chosen_entry.avg_bert_score
            reason = (
                f"Top semantic similarity (BERTScore F1: {score}) "
                f"across {chosen_entry.total_runs} runs on '{task_type.value}'"
            )
        else:
            chosen_entry = entries[0]
            reason = (
                f"No BERTScore recorded; recommended by win rate ({chosen_entry.win_rate}%) "
                f"across {chosen_entry.total_runs} runs."
            )
    elif metric == ScoringMetric.ROUGE_L:
        with_rouge = [e for e in entries if e.avg_rouge_l is not None]
        if with_rouge:
            chosen_entry = max(with_rouge, key=lambda e: e.avg_rouge_l or 0.0)
            score = chosen_entry.avg_rouge_l
            reason = (
                f"Top n-gram overlap (ROUGE-L: {score}) "
                f"across {chosen_entry.total_runs} runs on '{task_type.value}'"
            )
        else:
            chosen_entry = entries[0]
            reason = (
                f"No ROUGE-L recorded; recommended by win rate ({chosen_entry.win_rate}%) "
                f"across {chosen_entry.total_runs} runs."
            )
    elif metric == ScoringMetric.LATENCY:
        chosen_entry = min(entries, key=lambda e: e.avg_latency_ms)
        score = chosen_entry.avg_latency_ms
        reason = (
            f"Lowest average response latency ({score}ms) "
            f"across {chosen_entry.total_runs} runs on '{task_type.value}'"
        )
    elif metric == ScoringMetric.ESTIMATED_COST:
        chosen_entry = min(entries, key=lambda e: e.total_estimated_cost_usd)
        score = chosen_entry.total_estimated_cost_usd
        reason = (
            f"Lowest total inference expenditure (${score:.6f}) "
            f"across {chosen_entry.total_runs} runs on '{task_type.value}'"
        )
    else:
        # Default: highest win rate, tie-break by latency
        chosen_entry = max(entries, key=lambda e: (e.win_rate, -e.avg_latency_ms))
        score = chosen_entry.win_rate
        reason = (
            f"Leading win rate ({score}%) and avg latency ({chosen_entry.avg_latency_ms}ms) "
            f"across {chosen_entry.total_runs} runs on '{task_type.value}'"
        )

    return ModelRecommendation(
        task_type=task_type,
        recommended_model=chosen_entry.model_id,
        metric=metric,
        score=score,
        reason=reason,
    )
