"""API routes for sentence-level Hallucination Detection & factual consistency."""

import logging

from fastapi import APIRouter, HTTPException, status

from backend.schemas.hallucination import (
    HallucinationAnalysisRequest,
    HallucinationAnalysisResult,
)
from backend.services.hallucination import analyze_hallucination_details

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/eval/hallucination", tags=["Hallucination Detection"])


@router.post("", response_model=HallucinationAnalysisResult)
async def analyze_hallucination(
    request: HallucinationAnalysisRequest,
) -> HallucinationAnalysisResult:
    """Analyze candidate generation against source reference text for ungrounded claims."""
    try:
        return await analyze_hallucination_details(
            candidate_output=request.candidate_text,
            reference_text=request.reference_text,
        )
    except Exception as exc:
        logger.error(f"Hallucination inspection failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hallucination inspection failed: {exc}",
        ) from exc
