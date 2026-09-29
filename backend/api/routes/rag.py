"""API routes for RAG (Retrieval-Augmented Generation) pipeline evaluation."""

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.schemas.rag import RAGRunRequest, RAGRunResult, RAGScoreSchema
from backend.services.rag_eval import evaluate_rag_metrics, run_rag_evaluation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/eval/rag", tags=["RAG Evaluation"])


class RAGMetricsRequest(BaseModel):
    """Payload to evaluate tripartite RAG metrics on an existing answer."""

    query: str = Field(min_length=1, max_length=50000)
    contexts: list[str] = Field(min_length=1, max_length=50)
    answer: str = Field(min_length=1, max_length=50000)


@router.post("", response_model=RAGRunResult)
async def evaluate_rag_run(request: RAGRunRequest) -> RAGRunResult:
    """Benchmark candidate models on a RAG question answering task with retrieved contexts."""
    try:
        return await run_rag_evaluation(request)
    except Exception as exc:
        logger.error(f"RAG evaluation execution failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG evaluation failed: {exc}",
        ) from exc


@router.post("/metrics", response_model=RAGScoreSchema)
async def compute_rag_scores(request: RAGMetricsRequest) -> RAGScoreSchema:
    """Compute tripartite RAG metrics (Context Relevance, Faithfulness, Answer Relevance) on an answer."""
    try:
        return await evaluate_rag_metrics(
            query=request.query,
            contexts=request.contexts,
            answer=request.answer,
        )
    except Exception as exc:
        logger.error(f"RAG metric computation failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG metric computation failed: {exc}",
        ) from exc
