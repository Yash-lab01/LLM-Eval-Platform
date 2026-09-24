"""Unit tests for the Automated Scoring Service."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.middleware.feature_router import FeatureRouter
from backend.models.eval import EvalScoreORM
from backend.schemas.consumers import TaskType
from backend.schemas.eval import EvalScoreSchema, ModelResponseSchema
from backend.schemas.models import ModelID
from backend.services.scoring import (
    _fallback_token_f1,
    close_scoring_models,
    compute_bert_score,
    compute_cost_estimate,
    compute_rouge_l,
    determine_winner,
    init_scoring_models,
    score_run_responses,
)


def test_scoring_lifecycle():
    """Verify initialization and cleanup of scoring models."""
    init_scoring_models()
    close_scoring_models()


def test_rouge_l_computation():
    """Verify ROUGE-L computation on identical, overlapping, and disjoint texts."""
    # Identical text
    assert compute_rouge_l("The quick brown fox", "The quick brown fox") == 1.0

    # Partial overlap
    score = compute_rouge_l("The brown fox jumps", "The quick brown fox jumps over")
    assert 0.0 < score < 1.0

    # Disjoint text
    assert compute_rouge_l("Apple banana", "Cat dog elephant") == 0.0

    # Empty text
    assert compute_rouge_l("", "Some reference") == 0.0
    assert compute_rouge_l("Candidate", "") == 0.0


def test_cost_estimation():
    """Verify cost calculation across different model provider pricing tiers."""
    # Gemini 3.5 Flash: $0.00015 per 1k tokens
    cost_gemini = compute_cost_estimate(ModelID.GEMINI_3_5_FLASH.value, 1000)
    assert cost_gemini == 0.00015

    # Local Ollama: $0.00
    cost_ollama = compute_cost_estimate(ModelID.OLLAMA_LLAMA_3_2.value, 5000)
    assert cost_ollama == 0.0

    # Groq GPT-OSS 120B: $0.00050 per 1k tokens
    cost_groq = compute_cost_estimate(ModelID.GROQ_GPT_OSS_120B.value, 2000)
    assert cost_groq == 0.001


def test_fallback_token_f1():
    """Verify token F1 fallback calculation when PyTorch BERTScore is unavailable."""
    # Identical
    assert _fallback_token_f1("hello world", "hello world") == 1.0

    # Disjoint
    assert _fallback_token_f1("foo bar", "baz qux") == 0.0

    # Partial
    assert 0.0 < _fallback_token_f1("deep learning models", "learning models fast") < 1.0

    # Empty
    assert _fallback_token_f1("", "reference") == 0.0


@pytest.mark.asyncio
async def test_compute_bert_score_async_executor():
    """Verify BERTScore runs in executor and produces float metric."""
    score = await compute_bert_score("Python is high-level", "Python is a programming language")
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_determine_winner_with_semantic_scores():
    """Verify winner selection prefers high semantic quality with latency consideration."""
    responses = [
        ModelResponseSchema(
            model_id=ModelID.GEMINI_3_5_FLASH,
            output="Good high quality answer",
            latency_ms=250.0,
            token_count=50,
            created_at=datetime.now(UTC),
        ),
        ModelResponseSchema(
            model_id=ModelID.GROQ_GPT_OSS_20B,
            output="Mediocre answer",
            latency_ms=100.0,
            token_count=30,
            created_at=datetime.now(UTC),
        ),
    ]

    scores = [
        EvalScoreSchema(
            model_id=ModelID.GEMINI_3_5_FLASH,
            bert_score_f1=0.92,
            rouge_l=0.88,
            latency_ms=250.0,
            token_count=50,
        ),
        EvalScoreSchema(
            model_id=ModelID.GROQ_GPT_OSS_20B,
            bert_score_f1=0.45,
            rouge_l=0.40,
            latency_ms=100.0,
            token_count=30,
        ),
    ]

    winner = determine_winner(responses, scores)
    assert winner == ModelID.GEMINI_3_5_FLASH


def test_determine_winner_without_semantic_scores():
    """Verify winner selection defaults to lowest latency when semantic scores are absent."""
    responses = [
        ModelResponseSchema(
            model_id=ModelID.GEMINI_3_5_FLASH,
            output="Valid response A",
            latency_ms=300.0,
            token_count=40,
            created_at=datetime.now(UTC),
        ),
        ModelResponseSchema(
            model_id=ModelID.GROQ_GPT_OSS_20B,
            output="Valid response B",
            latency_ms=120.0,
            token_count=40,
            created_at=datetime.now(UTC),
        ),
    ]

    scores = [
        EvalScoreSchema(
            model_id=ModelID.GEMINI_3_5_FLASH,
            bert_score_f1=None,
            rouge_l=None,
            latency_ms=300.0,
            token_count=40,
        ),
        EvalScoreSchema(
            model_id=ModelID.GROQ_GPT_OSS_20B,
            bert_score_f1=None,
            rouge_l=None,
            latency_ms=120.0,
            token_count=40,
        ),
    ]

    winner = determine_winner(responses, scores)
    assert winner == ModelID.GROQ_GPT_OSS_20B


@pytest.mark.asyncio
async def test_score_run_responses_persists_to_db():
    """Verify score_run_responses executes enabled metrics and adds ORM records to session."""
    run_id = uuid.uuid4()
    router = FeatureRouter()
    responses = [
        ModelResponseSchema(
            model_id=ModelID.GEMINI_3_5_FLASH,
            output="Photosynthesis is the process by which green plants make food.",
            latency_ms=200.0,
            token_count=45,
            created_at=datetime.now(UTC),
        ),
        ModelResponseSchema(
            model_id=ModelID.GROQ_GPT_OSS_20B,
            output="Plants make food using sunlight and chlorophyll.",
            latency_ms=110.0,
            token_count=35,
            created_at=datetime.now(UTC),
        ),
    ]
    ref_output = "Photosynthesis is the process used by plants to convert sunlight into energy."

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    scores, winner = await score_run_responses(
        run_id=run_id,
        task_type=TaskType.QUESTION_ANSWERING,
        reference_output=ref_output,
        responses=responses,
        router=router,
        session=mock_session,
    )

    assert len(scores) == 2
    assert winner in [ModelID.GEMINI_3_5_FLASH, ModelID.GROQ_GPT_OSS_20B]
    assert mock_session.add.call_count == 2
    assert mock_session.commit.called

    first_score_orm = mock_session.add.call_args_list[0][0][0]
    assert isinstance(first_score_orm, EvalScoreORM)
    assert first_score_orm.run_id == run_id
    assert first_score_orm.bert_score_f1 is not None
    assert first_score_orm.rouge_l is not None
    assert first_score_orm.estimated_cost_usd > 0
