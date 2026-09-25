"""Run Comparison Service.

Computes metric deltas between two evaluation runs across shared models.
Calculates differences in BERTScore, ROUGE-L, latency, token count, and cost.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.eval import EvalRun
from backend.schemas.eval import RunComparison

logger = logging.getLogger(__name__)


async def compare_eval_runs(
    run_id_a: UUID,
    run_id_b: UUID,
    session: AsyncSession,
) -> RunComparison:
    """Compare performance metrics between two evaluation runs.

    Returns score_deltas calculated as (run_b - run_a), so positive numbers indicate
    an increase in the metric from run A to run B.
    """
    logger.info(f"Comparing evaluation runs {run_id_a} and {run_id_b}")

    query = select(EvalRun).options(selectinload(EvalRun.scores))

    res_a = await session.execute(query.where(EvalRun.id == run_id_a))
    run_a = res_a.scalar_one_or_none()
    if not run_a:
        raise ValueError(f"Evaluation run {run_id_a} not found")

    res_b = await session.execute(query.where(EvalRun.id == run_id_b))
    run_b = res_b.scalar_one_or_none()
    if not run_b:
        raise ValueError(f"Evaluation run {run_id_b} not found")

    scores_a = {s.model_id: s for s in run_a.scores}
    scores_b = {s.model_id: s for s in run_b.scores}

    all_models = sorted(set(scores_a.keys()).union(scores_b.keys()))
    score_deltas: dict[str, dict[str, float | None]] = {}

    for model_id in all_models:
        s_a = scores_a.get(model_id)
        s_b = scores_b.get(model_id)

        deltas: dict[str, float | None] = {}

        if s_a and s_b:
            deltas["bert_score_f1"] = (
                round(s_b.bert_score_f1 - s_a.bert_score_f1, 4)
                if s_b.bert_score_f1 is not None and s_a.bert_score_f1 is not None
                else None
            )
            deltas["rouge_l"] = (
                round(s_b.rouge_l - s_a.rouge_l, 4)
                if s_b.rouge_l is not None and s_a.rouge_l is not None
                else None
            )
            deltas["latency_ms"] = round(s_b.latency_ms - s_a.latency_ms, 2)
            deltas["token_count"] = float(s_b.token_count - s_a.token_count)
            deltas["estimated_cost_usd"] = round(s_b.estimated_cost_usd - s_a.estimated_cost_usd, 6)
        else:
            # Model only evaluated in one of the runs
            deltas["bert_score_f1"] = None
            deltas["rouge_l"] = None
            deltas["latency_ms"] = None
            deltas["token_count"] = None
            deltas["estimated_cost_usd"] = None

        score_deltas[model_id] = deltas

    return RunComparison(
        run_id_a=run_id_a,
        run_id_b=run_id_b,
        score_deltas=score_deltas,
    )
