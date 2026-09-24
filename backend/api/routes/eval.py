"""REST API endpoints for triggering evaluation runs, querying results, and viewing history."""

import logging
import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.middleware.auth import get_current_consumer
from backend.core.database import get_db
from backend.models.consumer import Consumer
from backend.models.eval import EvalRun
from backend.schemas.consumers import TaskType
from backend.schemas.eval import (
    EvalRunResult,
    EvalRunSummary,
    ModelResponseSchema,
    PromptRunRequest,
)
from backend.schemas.models import ModelID
from backend.services.eval_runner import run_parallel_eval
from backend.tasks.eval_tasks import run_eval_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/eval", tags=["Evaluation"])


@router.post(
    "/run",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger an evaluation run across multiple models",
)
async def create_eval_run(
    request: PromptRunRequest,
    background_tasks: BackgroundTasks,
    consumer: Annotated[Consumer | None, Depends(get_current_consumer)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> dict:
    """Validate request, initialize database record, and dispatch parallel execution."""
    run_id = uuid.uuid4()
    consumer_id = consumer.id if consumer else None

    # 1. Create initial run entry in PostgreSQL
    eval_run = EvalRun(
        id=run_id,
        consumer_id=consumer_id,
        prompt_text=request.prompt,
        task_type=request.task_type.value,
        models=[m.value for m in request.models],
        reference_output=request.reference_output,
        status="pending",
    )
    db.add(eval_run)
    await db.commit()

    # 2. Dispatch execution
    # Attempt to route via Celery; fall back to asyncio background task if broker is offline
    dispatched_celery = False
    try:
        run_eval_task.delay(str(run_id), request.model_dump(mode="json"))
        dispatched_celery = True
        logger.info(f"Dispatched run {run_id} to Celery eval_default queue")
    except Exception as exc:
        logger.warning(f"Celery dispatch failed ({exc}), falling back to async background task")

    if not dispatched_celery:
        # Resilient background execution fallback
        background_tasks.add_task(run_parallel_eval, run_id=run_id, request=request)

    return {
        "run_id": str(run_id),
        "status": "pending",
        "task_type": request.task_type.value,
        "models": [m.value for m in request.models],
        "stream_url": f"/ws/eval/{run_id}",
    }


@router.get(
    "/{run_id}",
    response_model=EvalRunResult,
    summary="Get full evaluation run results and responses",
)
async def get_eval_run(
    run_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EvalRunResult:
    """Retrieve evaluation run record with all model responses and computed scores."""
    stmt = (
        select(EvalRun)
        .where(EvalRun.id == run_id)
        .options(selectinload(EvalRun.responses), selectinload(EvalRun.scores))
    )
    result = await db.execute(stmt)
    run_record = result.scalar_one_or_none()

    if not run_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run {run_id} not found",
        )

    responses = [
        ModelResponseSchema(
            model_id=ModelID(r.model_id),
            output=r.output,
            latency_ms=r.latency_ms,
            token_count=r.token_count,
            finish_reason=r.finish_reason,
            from_cache=r.from_cache,
            attempt_number=r.attempt_number,
            created_at=r.created_at,
        )
        for r in run_record.responses
    ]

    return EvalRunResult(
        run_id=run_record.id,
        prompt=run_record.prompt_text,
        task_type=TaskType(run_record.task_type),
        models=[ModelID(m) for m in run_record.models],
        status=run_record.status,
        responses=responses,
        scores=[],
        winner=None,
        created_at=run_record.created_at,
        completed_at=run_record.completed_at,
    )


@router.get(
    "/history/list",
    response_model=list[EvalRunSummary],
    summary="List past evaluation runs",
)
async def list_eval_history(
    task_type: Annotated[TaskType | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> list[EvalRunSummary]:
    """Return paginated list of evaluation run summaries."""
    query = select(EvalRun).order_by(EvalRun.created_at.desc())
    if task_type:
        query = query.where(EvalRun.task_type == task_type.value)

    query = query.limit(limit).offset(offset)
    runs = (await db.execute(query)).scalars().all()

    return [
        EvalRunSummary(
            run_id=r.id,
            consumer_id=r.consumer_id,
            task_type=TaskType(r.task_type),
            models=[ModelID(m) for m in r.models],
            status=r.status,
            created_at=r.created_at,
            completed_at=r.completed_at,
        )
        for r in runs
    ]
