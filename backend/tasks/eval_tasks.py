"""Celery background tasks for evaluation execution and queue management."""

import asyncio
import logging
from uuid import UUID

from backend.core.celery_app import celery_app
from backend.schemas.eval import PromptRunRequest
from backend.services.eval_runner import run_parallel_eval

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    queue="eval_default",
)
def run_eval_task(self, run_id_str: str, request_data: dict) -> dict:
    """Execute asynchronous evaluation run within Celery worker.

    Validates request payload and triggers parallel model generation via LiteLLM.
    """
    logger.info(
        f"Celery task run_eval_task started for run {run_id_str} (attempt {self.request.retries})"
    )
    run_id = UUID(run_id_str)
    request = PromptRunRequest.model_validate(request_data)

    # Run the async evaluation engine in worker event loop
    result = asyncio.run(run_parallel_eval(run_id=run_id, request=request))

    logger.info(
        f"Celery task finished for run {run_id_str} with {len(result.responses)} model responses"
    )
    return {"run_id": run_id_str, "status": result.status, "responses_count": len(result.responses)}


@celery_app.task(
    bind=True,
    max_retries=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
    queue="eval_batch",
)
def run_batch_eval_task(self, batch_id_str: str) -> dict:
    """Execute asynchronous batch evaluation in Celery worker on eval_batch queue."""
    logger.info(
        f"Celery batch task started for batch {batch_id_str} (attempt {self.request.retries})"
    )
    from backend.services.batch_service import process_batch_job

    batch_id = UUID(batch_id_str)
    result = asyncio.run(process_batch_job(batch_id))

    logger.info(
        f"Celery batch task completed for {batch_id_str}: {result.completed_items}/{result.total_items} items"
    )
    return {
        "batch_id": batch_id_str,
        "status": result.status,
        "completed_items": result.completed_items,
        "failed_items": result.failed_items,
    }
