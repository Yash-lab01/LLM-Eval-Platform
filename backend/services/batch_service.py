"""Batch Evaluation Service.

Manages batch evaluation jobs across large sets of prompts,
stores progress and intermediate results, and exports results to CSV.
Supports Celery queue `eval_batch` with asyncio background task fallback.
"""

import csv
import io
import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.core.redis_client import get_redis_client
from backend.schemas.batch import (
    BatchItemResult,
    BatchPromptItem,
    BatchResultsResponse,
    BatchStatusResponse,
    BatchUploadRequest,
)
from backend.schemas.consumers import TaskType
from backend.schemas.eval import PromptRunRequest
from backend.schemas.models import ModelID
from backend.services.eval_runner import run_parallel_eval

logger = logging.getLogger(__name__)

# In-memory storage fallback for batches when Redis is unavailable
_BATCH_META_STORE: dict[str, dict] = {}
_BATCH_RESULTS_STORE: dict[str, list[dict]] = {}


def parse_batch_csv(content: str) -> list[BatchPromptItem]:
    """Parse CSV text content into validated BatchPromptItem records."""
    reader = csv.DictReader(io.StringIO(content))
    items: list[BatchPromptItem] = []
    for row in reader:
        norm_row = {str(k).strip().lower(): str(v).strip() for k, v in row.items() if k}
        prompt = norm_row.get("prompt") or norm_row.get("input") or norm_row.get("text")
        if not prompt:
            continue
        ref = (
            norm_row.get("reference_output")
            or norm_row.get("ground_truth")
            or norm_row.get("reference")
        )
        item_id = norm_row.get("id") or str(uuid4())[:8]
        items.append(BatchPromptItem(id=item_id, prompt=prompt, reference_output=ref or None))
    return items


def parse_batch_json(content: str) -> list[BatchPromptItem]:
    """Parse JSON text content into validated BatchPromptItem records."""
    data = json.loads(content)
    if isinstance(data, dict) and "items" in data:
        data = data["items"]
    if not isinstance(data, list):
        raise ValueError("JSON must contain an array of prompt items")

    items: list[BatchPromptItem] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        prompt = row.get("prompt") or row.get("input") or row.get("text")
        if not prompt:
            continue
        ref = row.get("reference_output") or row.get("ground_truth") or row.get("reference")
        item_id = row.get("id") or str(uuid4())[:8]
        items.append(
            BatchPromptItem(
                id=str(item_id),
                prompt=str(prompt),
                reference_output=str(ref) if ref else None,
            )
        )
    return items


async def create_batch_job(request: BatchUploadRequest) -> UUID:
    """Initialize a new batch evaluation record."""
    batch_id = uuid4()
    batch_id_str = str(batch_id)
    now = datetime.now(UTC)

    meta = {
        "batch_id": batch_id_str,
        "status": "pending",
        "task_type": request.task_type.value,
        "models": [m.value for m in request.models],
        "total_items": len(request.items),
        "completed_items": 0,
        "failed_items": 0,
        "created_at": now.isoformat(),
        "completed_at": None,
        "consumer_id": request.consumer_id,
        "items": [item.model_dump() for item in request.items],
    }

    _BATCH_META_STORE[batch_id_str] = meta
    _BATCH_RESULTS_STORE[batch_id_str] = []

    try:
        redis_client = get_redis_client()
        await redis_client.set(f"batch:{batch_id_str}:meta", json.dumps(meta))
        await redis_client.set(f"batch:{batch_id_str}:results", json.dumps([]))
    except Exception as exc:
        logger.debug(f"Failed to persist batch meta to Redis: {exc}")

    return batch_id


async def get_batch_status(batch_id: UUID) -> BatchStatusResponse | None:
    """Retrieve current progress status for a batch evaluation job."""
    batch_id_str = str(batch_id)
    meta = None

    try:
        redis_client = get_redis_client()
        raw = await redis_client.get(f"batch:{batch_id_str}:meta")
        if raw:
            meta = json.loads(raw)
    except Exception as exc:
        logger.debug(f"Redis get batch meta failed: {exc}")

    if not meta:
        meta = _BATCH_META_STORE.get(batch_id_str)

    if not meta:
        return None

    return BatchStatusResponse(
        batch_id=UUID(meta["batch_id"]),
        status=meta["status"],
        task_type=TaskType(meta["task_type"]),
        models=[ModelID(m) for m in meta["models"]],
        total_items=meta["total_items"],
        completed_items=meta["completed_items"],
        failed_items=meta["failed_items"],
        created_at=datetime.fromisoformat(meta["created_at"]),
        completed_at=(
            datetime.fromisoformat(meta["completed_at"]) if meta.get("completed_at") else None
        ),
    )


async def get_batch_results(batch_id: UUID) -> BatchResultsResponse | None:
    """Retrieve full evaluation outputs and scores for all items in a batch."""
    status_resp = await get_batch_status(batch_id)
    if not status_resp:
        return None

    batch_id_str = str(batch_id)
    raw_results = None

    try:
        redis_client = get_redis_client()
        cached = await redis_client.get(f"batch:{batch_id_str}:results")
        if cached:
            raw_results = json.loads(cached)
    except Exception as exc:
        logger.debug(f"Redis get batch results failed: {exc}")

    if raw_results is None:
        raw_results = _BATCH_RESULTS_STORE.get(batch_id_str, [])

    results = [BatchItemResult.model_validate(r) for r in raw_results]

    return BatchResultsResponse(
        batch_id=batch_id,
        status=status_resp.status,
        total_items=status_resp.total_items,
        completed_items=status_resp.completed_items,
        failed_items=status_resp.failed_items,
        results=results,
    )


async def process_batch_job(batch_id: UUID) -> BatchStatusResponse:
    """Execute evaluation for all items in a batch sequentially or in chunks."""
    batch_id_str = str(batch_id)
    meta = None

    try:
        redis_client = get_redis_client()
        raw = await redis_client.get(f"batch:{batch_id_str}:meta")
        if raw:
            meta = json.loads(raw)
    except Exception:
        pass

    if not meta:
        meta = _BATCH_META_STORE.get(batch_id_str)

    if not meta:
        raise ValueError(f"Batch {batch_id} not found")

    meta["status"] = "running"
    _BATCH_META_STORE[batch_id_str] = meta

    items_data = meta.get("items", [])
    models = [ModelID(m) for m in meta["models"]]
    task_type = TaskType(meta["task_type"])
    consumer_id = meta.get("consumer_id")

    results_list: list[dict] = _BATCH_RESULTS_STORE.get(batch_id_str, [])

    for item_data in items_data:
        item_id = item_data.get("id", str(uuid4())[:8])
        prompt_text = item_data["prompt"]
        ref_out = item_data.get("reference_output")

        item_run_id = uuid4()
        run_request = PromptRunRequest(
            prompt=prompt_text,
            task_type=task_type,
            models=models,
            consumer_id=consumer_id,
            reference_output=ref_out,
        )

        try:
            eval_result = await run_parallel_eval(run_id=item_run_id, request=run_request)
            scores_dicts = [s.model_dump() for s in eval_result.scores]
            item_res = BatchItemResult(
                item_id=item_id,
                prompt=prompt_text,
                reference_output=ref_out,
                run_id=str(item_run_id),
                winner=eval_result.winner.value if eval_result.winner else None,
                scores=scores_dicts,
                status="completed",
            )
            meta["completed_items"] += 1
        except Exception as exc:
            logger.error(f"Error evaluating batch item {item_id}: {exc}")
            item_res = BatchItemResult(
                item_id=item_id,
                prompt=prompt_text,
                reference_output=ref_out,
                run_id=str(item_run_id),
                winner=None,
                scores=[],
                status="failed",
                error_message=str(exc),
            )
            meta["failed_items"] += 1

        results_list.append(item_res.model_dump())
        _BATCH_RESULTS_STORE[batch_id_str] = results_list
        _BATCH_META_STORE[batch_id_str] = meta

        # Update Redis progress
        try:
            redis_client = get_redis_client()
            await redis_client.set(f"batch:{batch_id_str}:meta", json.dumps(meta))
            await redis_client.set(f"batch:{batch_id_str}:results", json.dumps(results_list))
        except Exception:
            pass

    meta["status"] = "completed"
    meta["completed_at"] = datetime.now(UTC).isoformat()
    _BATCH_META_STORE[batch_id_str] = meta

    try:
        redis_client = get_redis_client()
        await redis_client.set(f"batch:{batch_id_str}:meta", json.dumps(meta))
        await redis_client.set(f"batch:{batch_id_str}:results", json.dumps(results_list))
    except Exception:
        pass

    return (await get_batch_status(batch_id)) or BatchStatusResponse(
        batch_id=batch_id,
        status="completed",
        task_type=task_type,
        models=models,
        total_items=meta["total_items"],
        completed_items=meta["completed_items"],
        failed_items=meta["failed_items"],
        created_at=datetime.fromisoformat(meta["created_at"]),
        completed_at=datetime.fromisoformat(meta["completed_at"]),
    )


async def export_batch_as_csv(batch_id: UUID) -> str:
    """Generate a downloadable CSV report summarizing all evaluated items and model scores."""
    batch_res = await get_batch_results(batch_id)
    if not batch_res:
        raise ValueError(f"Batch {batch_id} not found")

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(
        [
            "item_id",
            "prompt",
            "reference_output",
            "run_id",
            "status",
            "winner",
            "model_id",
            "bert_score_f1",
            "rouge_l",
            "llm_judge_score",
            "latency_ms",
            "estimated_cost_usd",
        ]
    )

    for item in batch_res.results:
        if not item.scores:
            writer.writerow(
                [
                    item.item_id,
                    item.prompt,
                    item.reference_output or "",
                    item.run_id or "",
                    item.status,
                    item.winner or "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )
            continue

        for sc in item.scores:
            writer.writerow(
                [
                    item.item_id,
                    item.prompt,
                    item.reference_output or "",
                    item.run_id or "",
                    item.status,
                    item.winner or "",
                    sc.get("model_id", ""),
                    sc.get("bert_score_f1", ""),
                    sc.get("rouge_l", ""),
                    sc.get("llm_judge_score", ""),
                    sc.get("latency_ms", ""),
                    sc.get("estimated_cost_usd", ""),
                ]
            )

    return output.getvalue()
