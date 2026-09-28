"""API routes for Batch Evaluation: dataset upload, progress tracking, and CSV export."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)

from backend.core.limiter import limiter
from backend.schemas.batch import (
    BatchResultsResponse,
    BatchStatusResponse,
    BatchUploadRequest,
)
from backend.schemas.consumers import TaskType
from backend.schemas.models import ModelID
from backend.services.batch_service import (
    create_batch_job,
    export_batch_as_csv,
    get_batch_results,
    get_batch_status,
    parse_batch_csv,
    parse_batch_json,
    process_batch_job,
)
from backend.tasks.eval_tasks import run_batch_eval_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/batch", tags=["Batch Evaluation"])


@router.post("/upload-file", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def upload_batch_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File(...)],
    models: Annotated[str, Form(...)],  # Comma-separated or single model ID
    task_type: Annotated[str, Form(...)] = "question_answering",
) -> dict:
    """Upload a CSV or JSON dataset of prompts and initiate batch evaluation."""
    filename = file.filename or ""
    content_bytes = await file.read()
    content_str = content_bytes.decode("utf-8", errors="replace")

    # Parse items based on file extension
    try:
        if filename.endswith(".json"):
            items = parse_batch_json(content_str)
        else:
            items = parse_batch_csv(content_str)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse uploaded batch file: {exc}",
        ) from exc

    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File contains no valid prompt items",
        )

    # Parse models
    model_list: list[ModelID] = []
    for m in models.split(","):
        clean_m = m.strip()
        if clean_m:
            try:
                model_list.append(ModelID(clean_m))
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown model identifier: '{clean_m}'",
                ) from exc

    if not model_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one valid model must be specified",
        )

    try:
        t_type = TaskType(task_type)
    except ValueError:
        t_type = TaskType.QUESTION_ANSWERING

    upload_req = BatchUploadRequest(
        items=items,
        models=model_list,
        task_type=t_type,
    )

    batch_id = await create_batch_job(upload_req)

    # Dispatch via Celery eval_batch queue with asyncio background task fallback
    try:
        run_batch_eval_task.delay(str(batch_id))
        logger.info(f"Dispatched batch {batch_id} to Celery eval_batch queue")
    except Exception as exc:
        logger.warning(
            f"Celery dispatch failed for batch {batch_id} ({exc}), running background task"
        )
        background_tasks.add_task(process_batch_job, batch_id)

    return {
        "batch_id": str(batch_id),
        "status": "pending",
        "total_items": len(items),
        "task_type": t_type.value,
        "models": [m.value for m in model_list],
    }


@router.post("/create", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def create_batch(
    request: Request,
    payload: BatchUploadRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Initiate a batch evaluation job from a JSON payload."""
    batch_id = await create_batch_job(payload)

    try:
        run_batch_eval_task.delay(str(batch_id))
        logger.info(f"Dispatched batch {batch_id} to Celery eval_batch queue")
    except Exception as exc:
        logger.warning(
            f"Celery dispatch failed for batch {batch_id} ({exc}), running background task"
        )
        background_tasks.add_task(process_batch_job, batch_id)

    return {
        "batch_id": str(batch_id),
        "status": "pending",
        "total_items": len(payload.items),
        "task_type": payload.task_type.value,
        "models": [m.value for m in payload.models],
    }


@router.get("/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_progress(batch_id: UUID) -> BatchStatusResponse:
    """Retrieve execution progress and status for a batch evaluation job."""
    status_resp = await get_batch_status(batch_id)
    if not status_resp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found",
        )
    return status_resp


@router.get("/{batch_id}/results", response_model=BatchResultsResponse)
async def get_batch_detail_results(batch_id: UUID) -> BatchResultsResponse:
    """Retrieve complete per-item evaluation scores and outputs for a batch job."""
    results_resp = await get_batch_results(batch_id)
    if not results_resp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found",
        )
    return results_resp


@router.get("/{batch_id}/export")
async def export_batch_csv_report(batch_id: UUID) -> Response:
    """Download the batch evaluation results as a formatted CSV file."""
    try:
        csv_data = await export_batch_as_csv(batch_id)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=batch_{batch_id}_results.csv"},
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(f"Failed to export CSV for batch {batch_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate CSV export",
        ) from exc
