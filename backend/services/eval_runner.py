"""Evaluation Execution Engine.

Coordinates parallel model inference via LiteLLM using asyncio.gather,
publishes live token chunks to Redis pub/sub channels, and records results in PostgreSQL.
"""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import AsyncSessionFactory
from backend.core.redis_client import get_redis_client, run_status_channel, run_token_channel
from backend.middleware.feature_router import FeatureRouter
from backend.models.eval import EvalRun, ModelResponseORM
from backend.schemas.eval import (
    EvalRunResult,
    ModelResponseSchema,
    PromptRunRequest,
)
from backend.schemas.models import ModelID
from backend.services.leaderboard import invalidate_leaderboard_cache
from backend.services.litellm_client import stream_model_completion
from backend.services.observability import build_trace_metadata
from backend.services.scoring import score_run_responses

logger = logging.getLogger(__name__)


async def _stream_and_publish_model(
    run_id: UUID,
    model_id: ModelID,
    prompt: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Execute streaming for a single model and publish token events to Redis pub/sub."""
    run_id_str = str(run_id)
    model_str = model_id.value
    channel = run_token_channel(run_id_str, model_str)

    try:
        redis_client = get_redis_client()
    except Exception as exc:
        logger.warning(f"Failed to access Redis client in runner: {exc}")
        redis_client = None

    final_payload: dict[str, Any] | None = None

    async for chunk in stream_model_completion(
        run_id=run_id_str,
        model_id=model_str,
        prompt=prompt,
        metadata=metadata,
    ):
        if not chunk.get("is_final"):
            event = {
                "run_id": run_id_str,
                "model_id": model_str,
                "token": chunk.get("token", ""),
                "is_final": False,
            }
            if redis_client:
                try:
                    await redis_client.publish(channel, json.dumps(event))
                except Exception as pub_exc:
                    logger.debug(f"Redis publish error: {pub_exc}")
        else:
            final_payload = chunk
            event = {
                "run_id": run_id_str,
                "model_id": model_str,
                "output": chunk.get("output", ""),
                "latency_ms": chunk.get("latency_ms", 0.0),
                "token_count": chunk.get("token_count", 0),
                "finish_reason": chunk.get("finish_reason", "stop"),
                "is_final": True,
            }
            if redis_client:
                try:
                    await redis_client.publish(channel, json.dumps(event))
                except Exception as pub_exc:
                    logger.debug(f"Redis final publish error: {pub_exc}")

    if not final_payload:
        raise RuntimeError(f"Model stream ended without completion summary for {model_str}")

    return {
        "model_id": model_id,
        "output": final_payload["output"],
        "latency_ms": final_payload["latency_ms"],
        "token_count": final_payload["token_count"],
        "finish_reason": final_payload.get("finish_reason", "stop"),
        "attempt_number": final_payload.get("attempt_number", 1),
    }


async def run_parallel_eval(
    run_id: UUID,
    request: PromptRunRequest,
    session: AsyncSession | None = None,
) -> EvalRunResult:
    """Run all target models in parallel via asyncio.gather and record responses in PostgreSQL."""
    run_id_str = str(run_id)
    logger.info(
        f"Starting parallel evaluation for run {run_id_str} across {len(request.models)} models"
    )

    # Helper function to perform DB operations
    async def _process_eval(db: AsyncSession) -> EvalRunResult:
        # 1. Update run status to running
        await db.execute(update(EvalRun).where(EvalRun.id == run_id).values(status="running"))
        await db.commit()

        # Publish status event
        try:
            redis_client = get_redis_client()
            await redis_client.publish(
                run_status_channel(run_id_str),
                json.dumps({"run_id": run_id_str, "status": "running"}),
            )
        except Exception as exc:
            logger.debug(f"Status publish failed: {exc}")

        # 2. Launch parallel tasks using asyncio.gather
        tasks = [
            _stream_and_publish_model(
                run_id=run_id,
                model_id=model,
                prompt=request.prompt,
                metadata=build_trace_metadata(
                    run_id=run_id,
                    model_id=model.value,
                    task_type=request.task_type.value,
                    consumer_id=request.consumer_id,
                ),
            )
            for model in request.models
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        responses: list[ModelResponseSchema] = []
        for model_id, res in zip(request.models, results, strict=False):
            if isinstance(res, Exception):
                logger.error(f"Error evaluating model {model_id.value}: {res}")
                # Save partial failure response
                orm_resp = ModelResponseORM(
                    id=uuid.uuid4(),
                    run_id=run_id,
                    model_id=model_id.value,
                    output=f"Error: {res}",
                    latency_ms=0.0,
                    token_count=0,
                    finish_reason="error",
                    from_cache=False,
                )
            else:
                orm_resp = ModelResponseORM(
                    id=uuid.uuid4(),
                    run_id=run_id,
                    model_id=res["model_id"].value,
                    output=res["output"],
                    latency_ms=res["latency_ms"],
                    token_count=res["token_count"],
                    finish_reason=res["finish_reason"],
                    from_cache=False,
                    attempt_number=res["attempt_number"],
                )
                responses.append(
                    ModelResponseSchema(
                        model_id=model_id,
                        output=res["output"],
                        latency_ms=res["latency_ms"],
                        token_count=res["token_count"],
                        finish_reason=res["finish_reason"],
                        from_cache=False,
                        attempt_number=res["attempt_number"],
                        created_at=datetime.now(UTC),
                    )
                )
            db.add(orm_resp)

        # 3. Automated Scoring (Phase 3)
        router = FeatureRouter(request.consumer_config)
        scores, winner = await score_run_responses(
            run_id=run_id,
            task_type=request.task_type,
            reference_output=request.reference_output,
            responses=responses,
            router=router,
            session=db,
        )

        # Invalidate leaderboard cache for this task category
        await invalidate_leaderboard_cache(request.task_type)

        # 4. Mark run as completed
        completed_at = datetime.now(UTC)
        await db.execute(
            update(EvalRun)
            .where(EvalRun.id == run_id)
            .values(
                status="completed",
                completed_at=completed_at,
            )
        )
        await db.commit()

        # Publish final status event
        try:
            redis_client = get_redis_client()
            await redis_client.publish(
                run_status_channel(run_id_str),
                json.dumps({"run_id": run_id_str, "status": "completed"}),
            )
        except Exception as exc:
            logger.debug(f"Status publish failed: {exc}")

        # Fetch original run to populate full result
        run_record = (await db.execute(select(EvalRun).where(EvalRun.id == run_id))).scalar_one()

        return EvalRunResult(
            run_id=run_id,
            prompt=request.prompt,
            task_type=request.task_type,
            models=request.models,
            status="completed",
            responses=responses,
            scores=scores,
            winner=winner,
            created_at=run_record.created_at,
            completed_at=completed_at,
        )

    if session is not None:
        return await _process_eval(session)
    async with AsyncSessionFactory() as session:
        return await _process_eval(session)
