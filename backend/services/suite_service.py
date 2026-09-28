"""Regression Testing Suite Service.

Provides persistence for reusable prompt suites, manages automated suite runs,
and computes regression comparison reports with per-prompt metric deltas.
"""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.core.redis_client import get_redis_client
from backend.schemas.eval import PromptRunRequest
from backend.schemas.models import ModelID
from backend.schemas.suite import (
    MetricDelta,
    PromptRegressionDelta,
    PromptSuiteCreate,
    PromptSuiteSchema,
    RegressionReport,
    SuiteRunItemScore,
    SuiteRunRecord,
)
from backend.services.eval_runner import run_parallel_eval

logger = logging.getLogger(__name__)

# In-memory storage for suites and runs when Redis is offline
_SUITES_STORE: dict[str, dict] = {}
_SUITE_RUNS_STORE: dict[str, list[dict]] = {}


async def save_prompt_suite(create: PromptSuiteCreate) -> PromptSuiteSchema:
    """Create and persist a new prompt benchmark suite."""
    suite_id = uuid4()
    suite_id_str = str(suite_id)
    now = datetime.now(UTC)

    schema = PromptSuiteSchema(
        id=suite_id,
        name=create.name,
        description=create.description,
        task_type=create.task_type,
        prompts=create.prompts,
        created_at=now,
    )

    data = schema.model_dump(mode="json")
    _SUITES_STORE[suite_id_str] = data
    _SUITE_RUNS_STORE[suite_id_str] = []

    try:
        redis_client = get_redis_client()
        await redis_client.set(f"suite:{suite_id_str}", json.dumps(data))
    except Exception as exc:
        logger.debug(f"Failed to persist suite to Redis: {exc}")

    return schema


async def get_prompt_suite(suite_id: UUID) -> PromptSuiteSchema | None:
    """Retrieve a prompt suite by unique identifier."""
    suite_id_str = str(suite_id)
    data = None

    try:
        redis_client = get_redis_client()
        raw = await redis_client.get(f"suite:{suite_id_str}")
        if raw:
            data = json.loads(raw)
    except Exception as exc:
        logger.debug(f"Redis get suite failed: {exc}")

    if not data:
        data = _SUITES_STORE.get(suite_id_str)

    if not data:
        return None

    return PromptSuiteSchema.model_validate(data)


async def list_prompt_suites() -> list[PromptSuiteSchema]:
    """List all persisted benchmark prompt suites."""
    suites = []
    for data in _SUITES_STORE.values():
        suites.append(PromptSuiteSchema.model_validate(data))
    return suites


async def run_prompt_suite(
    suite_id: UUID,
    models: list[ModelID],
    consumer_id: str | None = None,
) -> SuiteRunRecord:
    """Execute all prompts in a suite across target models and record scores."""
    suite = await get_prompt_suite(suite_id)
    if not suite:
        raise ValueError(f"Prompt suite {suite_id} not found")

    run_id = uuid4()
    item_scores: list[SuiteRunItemScore] = []

    for prompt_item in suite.prompts:
        item_run_id = uuid4()
        req = PromptRunRequest(
            prompt=prompt_item.prompt,
            task_type=suite.task_type,
            models=models,
            consumer_id=consumer_id,
            reference_output=prompt_item.reference_output,
        )

        try:
            eval_res = await run_parallel_eval(run_id=item_run_id, request=req)
            for score in eval_res.scores:
                item_scores.append(
                    SuiteRunItemScore(
                        prompt_id=prompt_item.id,
                        prompt=prompt_item.prompt,
                        model_id=score.model_id,
                        bert_score_f1=score.bert_score_f1,
                        rouge_l=score.rouge_l,
                        llm_judge_score=score.llm_judge_score,
                        latency_ms=score.latency_ms,
                    )
                )
        except Exception as exc:
            logger.error(f"Error evaluating suite prompt {prompt_item.id}: {exc}")

    record = SuiteRunRecord(
        run_id=run_id,
        suite_id=suite_id,
        models=models,
        timestamp=datetime.now(UTC),
        item_scores=item_scores,
    )

    suite_id_str = str(suite_id)
    runs_list = _SUITE_RUNS_STORE.get(suite_id_str, [])
    runs_list.append(record.model_dump(mode="json"))
    _SUITE_RUNS_STORE[suite_id_str] = runs_list

    try:
        redis_client = get_redis_client()
        await redis_client.set(f"suite_runs:{suite_id_str}", json.dumps(runs_list))
    except Exception as exc:
        logger.debug(f"Redis persist suite runs failed: {exc}")

    return record


async def list_suite_runs(suite_id: UUID) -> list[SuiteRunRecord]:
    """Retrieve all executed runs recorded for a prompt suite."""
    suite_id_str = str(suite_id)
    raw_runs = None

    try:
        redis_client = get_redis_client()
        cached = await redis_client.get(f"suite_runs:{suite_id_str}")
        if cached:
            raw_runs = json.loads(cached)
    except Exception:
        pass

    if raw_runs is None:
        raw_runs = _SUITE_RUNS_STORE.get(suite_id_str, [])

    return [SuiteRunRecord.model_validate(r) for r in raw_runs]


async def generate_regression_report(
    suite_id: UUID,
    baseline_run_id: UUID,
    candidate_run_id: UUID,
) -> RegressionReport:
    """Compare two suite runs, compute metric deltas per prompt, and flag regressions."""
    runs = await list_suite_runs(suite_id)
    run_map = {r.run_id: r for r in runs}

    baseline_run = run_map.get(baseline_run_id)
    candidate_run = run_map.get(candidate_run_id)

    if not baseline_run or not candidate_run:
        raise ValueError(
            f"Run records not found for baseline ({baseline_run_id}) or candidate ({candidate_run_id})"
        )

    # Index scores: (prompt_id, model_id) -> SuiteRunItemScore
    base_scores = {(s.prompt_id, s.model_id): s for s in baseline_run.item_scores}
    cand_scores = {(s.prompt_id, s.model_id): s for s in candidate_run.item_scores}

    deltas: list[PromptRegressionDelta] = []
    improved_count = 0
    degraded_count = 0
    unchanged_count = 0
    quality_deltas_sum = 0.0

    all_keys = set(base_scores.keys()).union(cand_scores.keys())

    for prompt_id, model_id in sorted(all_keys, key=lambda k: k[0]):
        base_item = base_scores.get((prompt_id, model_id))
        cand_item = cand_scores.get((prompt_id, model_id))

        prompt_text = (
            cand_item.prompt if cand_item else (base_item.prompt if base_item else "Unknown prompt")
        )

        metrics: dict[str, MetricDelta] = {}
        net_item_delta = 0.0
        metric_count = 0

        # BERTScore delta
        b_bert = base_item.bert_score_f1 if base_item else None
        c_bert = cand_item.bert_score_f1 if cand_item else None
        if b_bert is not None or c_bert is not None:
            d = (c_bert or 0.0) - (b_bert or 0.0)
            metrics["bert_score_f1"] = MetricDelta(
                baseline=b_bert, candidate=c_bert, delta=round(d, 4)
            )
            net_item_delta += d
            metric_count += 1

        # ROUGE-L delta
        b_rouge = base_item.rouge_l if base_item else None
        c_rouge = cand_item.rouge_l if cand_item else None
        if b_rouge is not None or c_rouge is not None:
            d = (c_rouge or 0.0) - (b_rouge or 0.0)
            metrics["rouge_l"] = MetricDelta(baseline=b_rouge, candidate=c_rouge, delta=round(d, 4))
            net_item_delta += d
            metric_count += 1

        # LLM Judge delta
        b_judge = base_item.llm_judge_score if base_item else None
        c_judge = cand_item.llm_judge_score if cand_item else None
        if b_judge is not None or c_judge is not None:
            d = (c_judge or 0.0) - (b_judge or 0.0)
            metrics["llm_judge_score"] = MetricDelta(
                baseline=b_judge, candidate=c_judge, delta=round(d, 4)
            )
            net_item_delta += d
            metric_count += 1

        # Latency delta (lower is better, so baseline - candidate)
        b_lat = base_item.latency_ms if base_item else None
        c_lat = cand_item.latency_ms if cand_item else None
        if b_lat is not None or c_lat is not None:
            lat_delta = (c_lat or 0.0) - (b_lat or 0.0)
            metrics["latency_ms"] = MetricDelta(
                baseline=b_lat, candidate=c_lat, delta=round(lat_delta, 2)
            )

        avg_quality_delta = net_item_delta / metric_count if metric_count > 0 else 0.0
        quality_deltas_sum += avg_quality_delta

        if avg_quality_delta > 0.02:
            item_status = "improved"
            improved_count += 1
        elif avg_quality_delta < -0.02:
            item_status = "degraded"
            degraded_count += 1
        else:
            item_status = "unchanged"
            unchanged_count += 1

        deltas.append(
            PromptRegressionDelta(
                prompt_id=prompt_id,
                prompt=prompt_text,
                model_id=model_id,
                metrics=metrics,
                status=item_status,
            )
        )

    net_overall_quality = round(quality_deltas_sum / len(deltas), 4) if deltas else 0.0

    return RegressionReport(
        suite_id=suite_id,
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        total_prompts=len(deltas),
        improved_count=improved_count,
        degraded_count=degraded_count,
        unchanged_count=unchanged_count,
        net_quality_delta=net_overall_quality,
        deltas=deltas,
    )
