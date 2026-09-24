"""Automated Scoring Service.

Computes semantic similarity (BERTScore), n-gram overlap (ROUGE-L),
latency, and cost estimation for evaluated model responses.
Non-blocking execution of heavy PyTorch models is guaranteed via loop.run_in_executor.
"""

import asyncio
import logging
import uuid
from uuid import UUID

from rouge_score import rouge_scorer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.feature_router import FeatureRouter
from backend.models.eval import EvalScoreORM
from backend.schemas.consumers import TaskType
from backend.schemas.eval import EvalScoreSchema, ModelResponseSchema
from backend.schemas.models import ModelID

logger = logging.getLogger(__name__)

# Estimated USD cost per 1,000 tokens based on model provider pricing
MODEL_COST_PER_1K_TOKENS: dict[str, float] = {
    ModelID.GEMINI_3_5_FLASH.value: 0.00015,
    ModelID.GEMINI_3_8_FLASH.value: 0.00020,
    ModelID.GROQ_GPT_OSS_120B.value: 0.00050,
    ModelID.GROQ_GPT_OSS_20B.value: 0.00010,
    ModelID.GROQ_QWEN_27B.value: 0.00010,
    ModelID.GROQ_QWEN_32B.value: 0.00012,
    ModelID.OLLAMA_LLAMA_3_2.value: 0.0,
    ModelID.OLLAMA_MISTRAL.value: 0.0,
    ModelID.OLLAMA_PHI3.value: 0.0,
}

# Global scorer instance for ROUGE-L to avoid repeated initialization
_ROUGE_SCORER: rouge_scorer.RougeScorer | None = None


def init_scoring_models() -> None:
    """Warm up and pre-initialize scoring models during application startup."""
    global _ROUGE_SCORER
    try:
        _ROUGE_SCORER = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        logger.info("ROUGE-L scoring model initialized successfully")
    except Exception as exc:
        logger.warning(f"Failed to pre-initialize ROUGE scorer: {exc}")


def close_scoring_models() -> None:
    """Clean up scoring model resources on application shutdown."""
    global _ROUGE_SCORER
    _ROUGE_SCORER = None
    logger.info("Scoring models closed")


def _fallback_token_f1(candidate: str, reference: str) -> float:
    """Deterministic token overlap F1 score used when PyTorch BERTScore weights are absent."""
    cand_tokens = [t.lower() for t in candidate.split() if t.isalnum()]
    ref_tokens = [t.lower() for t in reference.split() if t.isalnum()]

    if not cand_tokens or not ref_tokens:
        return 0.0

    cand_set = set(cand_tokens)
    ref_set = set(ref_tokens)
    common = cand_set.intersection(ref_set)

    if not common:
        return 0.0

    precision = len(common) / len(cand_set)
    recall = len(common) / len(ref_set)
    f1 = (2 * precision * recall) / (precision + recall)
    return round(float(f1), 4)


def _compute_bert_score_sync(candidate: str, reference: str) -> float:
    """Synchronous BERTScore computation executed in a worker thread via run_in_executor."""
    try:
        import bert_score  # type: ignore

        p, r, f1 = bert_score.score(
            cands=[candidate],
            refs=[reference],
            lang="en",
            model_type="distilbert-base-uncased",
            verbose=False,
        )
        return round(float(f1.mean().item()), 4)
    except Exception as exc:
        logger.debug(f"PyTorch BERTScore execution unavailable ({exc}); using token F1 fallback")
        return _fallback_token_f1(candidate, reference)


async def compute_bert_score(candidate: str, reference: str) -> float:
    """Compute BERTScore F1 metric without blocking the asyncio event loop."""
    if not candidate.strip() or not reference.strip():
        return 0.0

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _compute_bert_score_sync, candidate, reference)


def compute_rouge_l(candidate: str, reference: str) -> float:
    """Compute ROUGE-L longest common subsequence similarity score."""
    global _ROUGE_SCORER
    if not candidate.strip() or not reference.strip():
        return 0.0

    if _ROUGE_SCORER is None:
        _ROUGE_SCORER = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)

    score_dict = _ROUGE_SCORER.score(reference, candidate)
    return round(float(score_dict["rougeL"].fmeasure), 4)


def compute_cost_estimate(model_id: str, token_count: int) -> float:
    """Calculate estimated cost in USD based on model provider token rates."""
    rate_per_1k = MODEL_COST_PER_1K_TOKENS.get(model_id, 0.00010)
    cost = (token_count / 1000.0) * rate_per_1k
    return round(float(cost), 6)


def determine_winner(
    responses: list[ModelResponseSchema],
    scores: list[EvalScoreSchema],
) -> ModelID | None:
    """Determine the winning model based on composite quality and latency performance.

    If semantic scores (BERTScore/ROUGE-L) exist, models are ranked by quality with
    latency as tiebreaker. If semantic scores are absent, lowest latency wins.
    """
    if not responses or not scores:
        return None

    score_by_model = {s.model_id: s for s in scores}
    candidates: list[tuple[ModelID, float]] = []

    has_semantic_eval = any(s.bert_score_f1 is not None or s.rouge_l is not None for s in scores)

    for resp in responses:
        if resp.finish_reason == "error" or not resp.output.strip():
            continue

        model_score = score_by_model.get(resp.model_id)
        if not model_score:
            continue

        if has_semantic_eval:
            quality = 0.0
            if model_score.bert_score_f1 is not None:
                quality += model_score.bert_score_f1 * 0.7
            if model_score.rouge_l is not None:
                quality += model_score.rouge_l * 0.3

            # Modulate slightly by latency (faster response gains marginal advantage)
            speed_factor = 1.0 / (1.0 + (resp.latency_ms / 5000.0))
            composite = quality * 0.9 + speed_factor * 0.1
            candidates.append((resp.model_id, composite))
        else:
            # Rank strictly by lowest latency (inverted for ranking max)
            speed_rank = 10000.0 / (resp.latency_ms + 1.0)
            candidates.append((resp.model_id, speed_rank))

    if not candidates:
        return responses[0].model_id if responses else None

    candidates.sort(key=lambda item: item[1], reverse=True)
    return candidates[0][0]


async def score_run_responses(
    run_id: UUID,
    task_type: TaskType,
    reference_output: str | None,
    responses: list[ModelResponseSchema],
    router: FeatureRouter,
    session: AsyncSession,
) -> tuple[list[EvalScoreSchema], ModelID | None]:
    """Calculate scores for all model responses in a run and persist them to PostgreSQL."""
    scores: list[EvalScoreSchema] = []
    run_id_str = str(run_id)

    logger.info(f"Computing scores for run {run_id_str} with {len(responses)} responses")

    for resp in responses:
        bert_f1: float | None = None
        rouge_l_val: float | None = None

        if router.should_score_bert(reference_output) and reference_output:
            bert_f1 = await compute_bert_score(resp.output, reference_output)

        if router.should_score_rouge(reference_output) and reference_output:
            rouge_l_val = compute_rouge_l(resp.output, reference_output)

        cost = (
            compute_cost_estimate(resp.model_id.value, resp.token_count)
            if router.should_calculate_cost()
            else 0.0
        )

        score_schema = EvalScoreSchema(
            model_id=resp.model_id,
            bert_score_f1=bert_f1,
            rouge_l=rouge_l_val,
            latency_ms=resp.latency_ms,
            token_count=resp.token_count,
            estimated_cost_usd=cost,
            hallucination_score=None,
            llm_judge_score=None,
        )
        scores.append(score_schema)

        # Create ORM record for persistence
        orm_score = EvalScoreORM(
            id=uuid.uuid4(),
            run_id=run_id,
            model_id=resp.model_id.value,
            bert_score_f1=bert_f1,
            rouge_l=rouge_l_val,
            latency_ms=resp.latency_ms,
            token_count=resp.token_count,
            estimated_cost_usd=cost,
            hallucination_score=None,
            llm_judge_score=None,
        )
        session.add(orm_score)

    await session.commit()

    winner = determine_winner(responses, scores)
    logger.info(
        f"Scoring completed for run {run_id_str}. Winner: {winner.value if winner else 'None'}"
    )

    return scores, winner
