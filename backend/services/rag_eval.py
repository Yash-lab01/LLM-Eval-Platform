"""RAG Evaluation Engine.

Evaluates Retrieval-Augmented Generation systems using tripartite metrics:
1. Context Relevance: How pertinent the retrieved context passages are to the query.
2. Faithfulness: How grounded the generated answer is in the retrieved passages (1 - hallucination).
3. Answer Relevance: How well the generated answer directly resolves the query.
"""

import asyncio
import logging
import re
from uuid import uuid4

from backend.schemas.models import ModelID
from backend.schemas.rag import (
    RAGModelResult,
    RAGRunRequest,
    RAGRunResult,
    RAGScoreSchema,
)
from backend.services.hallucination import compute_hallucination_score
from backend.services.litellm_client import generate_model_response
from backend.services.scoring import compute_bert_score

logger = logging.getLogger(__name__)


def _compute_context_relevance_sync(query: str, contexts: list[str]) -> float:
    """Compute lexical and semantic overlap between query and retrieved context chunks."""
    if not query.strip() or not contexts:
        return 0.0

    combined_context = " ".join(contexts).lower()
    query_tokens = [w.lower() for w in re.findall(r"\b\w+\b", query) if len(w) > 2]
    if not query_tokens:
        return 0.5

    matched = sum(1 for w in query_tokens if w in combined_context)
    coverage = matched / len(query_tokens)
    return round(float(min(1.0, max(0.0, coverage))), 4)


async def compute_context_relevance(query: str, contexts: list[str]) -> float:
    """Compute context relevance score asynchronously."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _compute_context_relevance_sync, query, contexts)


async def compute_faithfulness(answer: str, contexts: list[str]) -> float:
    """Measure answer grounding against combined context passages (1.0 - hallucination risk)."""
    if not answer.strip():
        return 0.0
    if not contexts:
        return 0.0

    combined_context = "\n\n".join(contexts)
    hallucination_risk = await compute_hallucination_score(answer, combined_context)
    faithfulness = 1.0 - hallucination_risk
    return round(float(min(1.0, max(0.0, faithfulness))), 4)


async def compute_answer_relevance(query: str, answer: str) -> float:
    """Evaluate semantic alignment between user question and generated answer."""
    if not query.strip() or not answer.strip():
        return 0.0

    bert_f1 = await compute_bert_score(answer, query)
    return round(float(min(1.0, max(0.0, bert_f1))), 4)


async def evaluate_rag_metrics(query: str, contexts: list[str], answer: str) -> RAGScoreSchema:
    """Compute all three RAG evaluation metrics and their weighted composite score."""
    ctx_rel_task = compute_context_relevance(query, contexts)
    faith_task = compute_faithfulness(answer, contexts)
    ans_rel_task = compute_answer_relevance(query, answer)

    ctx_rel, faith, ans_rel = await asyncio.gather(ctx_rel_task, faith_task, ans_rel_task)

    composite = (ctx_rel * 0.30) + (faith * 0.40) + (ans_rel * 0.30)
    return RAGScoreSchema(
        context_relevance=ctx_rel,
        faithfulness=faith,
        answer_relevance=ans_rel,
        composite_score=round(float(composite), 4),
    )


async def run_rag_evaluation(request: RAGRunRequest) -> RAGRunResult:
    """Execute end-to-end RAG benchmark across target models."""
    run_id = uuid4()
    context_block = "\n---\n".join(request.contexts)
    rag_prompt = (
        f"You are a helpful assistant answering the question using ONLY the provided context passages.\n\n"
        f"Context Passages:\n{context_block}\n\n"
        f"Question:\n{request.query}\n\n"
        f"Answer:"
    )

    results: list[RAGModelResult] = []

    async def _eval_model(model_id: ModelID) -> RAGModelResult:
        resp = await generate_model_response(
            model_id=model_id,
            prompt=rag_prompt,
        )
        scores = await evaluate_rag_metrics(
            query=request.query,
            contexts=request.contexts,
            answer=resp.output,
        )
        return RAGModelResult(
            model_id=model_id,
            answer=resp.output,
            latency_ms=resp.latency_ms,
            token_count=resp.token_count,
            scores=scores,
        )

    # Parallel generation and scoring across all benchmarked models
    eval_tasks = [_eval_model(m) for m in request.models]
    model_results = await asyncio.gather(*eval_tasks, return_exceptions=True)

    for item in model_results:
        if isinstance(item, RAGModelResult):
            results.append(item)
        else:
            logger.error(f"RAG model evaluation task failed: {item}")

    winner: ModelID | None = None
    if results:
        # Sort by composite RAG quality score descending, with latency as tiebreaker
        results.sort(
            key=lambda r: (r.scores.composite_score, -r.latency_ms),
            reverse=True,
        )
        winner = results[0].model_id

    return RAGRunResult(
        run_id=run_id,
        query=request.query,
        contexts=request.contexts,
        results=results,
        winner=winner,
    )
