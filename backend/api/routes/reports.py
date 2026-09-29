"""API routes for Executive Evaluation Reports in HTML and PDF formats."""

import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.database import get_db
from backend.models.eval import EvalRun
from backend.schemas.consumers import TaskType
from backend.schemas.eval import EvalRunResult, EvalScoreSchema, ModelResponseSchema
from backend.schemas.models import ModelID
from backend.services.report_service import generate_pdf_report, render_html_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/eval", tags=["Evaluation Reports"])


async def _fetch_run_result(run_id: UUID, db: AsyncSession) -> EvalRunResult:
    """Fetch run with responses and scores and build EvalRunResult schema."""
    stmt = (
        select(EvalRun)
        .options(
            selectinload(EvalRun.responses),
            selectinload(EvalRun.scores),
        )
        .where(EvalRun.id == run_id)
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
            finish_reason=r.finish_reason or "stop",
            from_cache=bool(r.from_cache),
            attempt_number=r.attempt_number or 1,
            created_at=r.created_at or datetime.now(UTC),
        )
        for r in run_record.responses
    ]

    scores = [
        EvalScoreSchema(
            model_id=ModelID(s.model_id),
            bert_score_f1=s.bert_score_f1,
            rouge_l=s.rouge_l,
            latency_ms=s.latency_ms or 0.0,
            token_count=s.token_count or 0,
            estimated_cost_usd=s.estimated_cost_usd or 0.0,
            hallucination_score=s.hallucination_score,
            llm_judge_score=s.llm_judge_score,
        )
        for s in run_record.scores
    ]

    winner = None
    if scores:
        from backend.services.scoring import determine_winner

        winner = determine_winner(responses, scores)

    return EvalRunResult(
        run_id=run_record.id,
        prompt=run_record.prompt_text,
        task_type=TaskType(run_record.task_type),
        models=[ModelID(m) for m in run_record.models],
        status=run_record.status,
        responses=responses,
        scores=scores,
        winner=winner,
        created_at=run_record.created_at,
        completed_at=run_record.completed_at,
    )


@router.get("/{run_id}/export/html", response_class=HTMLResponse)
async def export_html_report(
    run_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    """Download executive evaluation benchmark summary as a standalone HTML document."""
    run_result = await _fetch_run_result(run_id, db)
    html_content = render_html_report(run_result)
    return HTMLResponse(content=html_content)


@router.get("/{run_id}/export/pdf")
async def export_pdf_report(
    run_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Download executive evaluation benchmark summary as a compiled PDF document."""
    run_result = await _fetch_run_result(run_id, db)
    pdf_bytes = generate_pdf_report(run_result)

    if pdf_bytes:
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=eval_report_{run_id}.pdf"},
        )

    # Fallback to HTML if PDF compiler is not available on host system
    html_content = render_html_report(run_result)
    return HTMLResponse(
        content=html_content,
        headers={"Content-Disposition": f"inline; filename=eval_report_{run_id}.html"},
    )
