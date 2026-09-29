"""API routes for 2D Embedding Projection & Visualizer."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.database import get_db
from backend.models.eval import EvalRun
from backend.schemas.visualizer import (
    EmbeddingVisualizationRequest,
    EmbeddingVisualizationResponse,
)
from backend.services.visualizer import generate_2d_embeddings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Embedding Visualizer"])


@router.post(
    "/visualizer/embeddings",
    response_model=EmbeddingVisualizationResponse,
)
async def compute_custom_visualizer_embeddings(
    request: EmbeddingVisualizationRequest,
) -> EmbeddingVisualizationResponse:
    """Compute 2D coordinate clusters and similarity matrix for arbitrary candidate texts."""
    try:
        return generate_2d_embeddings(
            prompt=request.prompt,
            candidate_responses=request.candidate_responses,
            reference_output=request.reference_output,
        )
    except Exception as exc:
        logger.error(f"Error computing visualizer embeddings: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate 2D embeddings: {exc}",
        ) from exc


@router.get(
    "/eval/{run_id}/visualizer",
    response_model=EmbeddingVisualizationResponse,
)
async def get_run_visualizer_embeddings(
    run_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EmbeddingVisualizationResponse:
    """Generate 2D coordinate clusters for an executed evaluation run."""
    stmt = select(EvalRun).options(selectinload(EvalRun.responses)).where(EvalRun.id == run_id)
    result = await db.execute(stmt)
    run_record = result.scalar_one_or_none()

    if not run_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run {run_id} not found",
        )

    candidate_responses = {
        resp.model_id: resp.output
        for resp in run_record.responses
        if resp.output and resp.finish_reason != "error"
    }

    if not candidate_responses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid candidate model outputs found for this run",
        )

    return generate_2d_embeddings(
        prompt=run_record.prompt_text,
        candidate_responses=candidate_responses,
        reference_output=run_record.reference_output,
    )
