"""Unit tests for Hallucination Detection service and sentence-level NLI scoring."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.middleware.feature_router import FeatureRouter
from backend.schemas.consumers import EvalConsumerConfig, FeatureFlag, TaskType
from backend.schemas.eval import EvalScoreSchema, ModelResponseSchema
from backend.schemas.models import ModelID
from backend.services.hallucination import (
    analyze_hallucination_details,
    compute_hallucination_score,
    split_into_sentences,
)
from backend.services.scoring import determine_winner, score_run_responses


def test_sentence_splitting():
    """Verify paragraph text is cleanly split into individual grammatical sentences."""
    text = (
        "The Apollo program was conceived in 1960. It succeeded in landing the first humans on the Moon in 1969! "
        "Neil Armstrong was the commander. Did they bring back lunar samples? Yes, they brought back 382 kilograms."
    )
    sentences = split_into_sentences(text)
    assert len(sentences) == 5
    assert "The Apollo program was conceived in 1960." in sentences
    assert "Neil Armstrong was the commander." in sentences


@pytest.mark.asyncio
async def test_hallucination_score_grounded():
    """Verify factual response consistent with reference yields low hallucination risk."""
    reference = "Paris is the capital of France. The Eiffel Tower was constructed in 1889 for the World's Fair."
    candidate = (
        "Paris is France's capital city. The Eiffel Tower was built in 1889 for the World's Fair."
    )

    score = await compute_hallucination_score(candidate, reference)
    assert score <= 0.30

    analysis = await analyze_hallucination_details(candidate, reference)
    assert not analysis.is_hallucinating
    assert analysis.overall_hallucination_score <= 0.30
    assert analysis.total_sentences >= 1


@pytest.mark.asyncio
async def test_hallucination_score_contradiction():
    """Verify contradictory statements with false negations or fabricated facts yield high risk."""
    reference = "The speed of light in vacuum is approximately 300,000 kilometers per second. Photons have zero rest mass."
    candidate = (
        "The speed of light is not 300,000 kilometers per second. "
        "Photons have enormous heavy mass and cannot travel through vacuum."
    )

    score = await compute_hallucination_score(candidate, reference)
    assert score >= 0.40

    analysis = await analyze_hallucination_details(candidate, reference)
    assert analysis.is_hallucinating
    assert analysis.flagged_sentences >= 1


@pytest.mark.asyncio
async def test_scoring_pipeline_hallucination_integration():
    """Verify score_run_responses populates hallucination_score when feature flag is active."""
    router = FeatureRouter(
        EvalConsumerConfig(
            consumer_id="hallucination-test-consumer",
            features=[FeatureFlag.HALLUCINATION_DETECTION],
            models=[ModelID.GEMINI_3_5_FLASH],
            task_type=TaskType.QUESTION_ANSWERING,
            scoring_metrics=[],
        )
    )

    reference = "Python was created by Guido van Rossum and released in 1991."
    responses = [
        ModelResponseSchema(
            model_id=ModelID.GEMINI_3_5_FLASH,
            output="Guido van Rossum created Python, releasing it in 1991.",
            latency_ms=180.0,
            token_count=35,
            finish_reason="stop",
        )
    ]

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    scores, _ = await score_run_responses(
        run_id=uuid4(),
        task_type=TaskType.QUESTION_ANSWERING,
        reference_output=reference,
        responses=responses,
        router=router,
        session=mock_db,
    )

    assert len(scores) == 1
    assert scores[0].hallucination_score is not None
    assert 0.0 <= scores[0].hallucination_score <= 1.0


def test_determine_winner_penalizes_hallucinating_model():
    """Verify determine_winner prefers a grounded model over a hallucinating model."""
    responses = [
        ModelResponseSchema(
            model_id=ModelID.GEMINI_3_5_FLASH,
            output="Grounded factual answer",
            latency_ms=200.0,
            token_count=40,
        ),
        ModelResponseSchema(
            model_id=ModelID.GROQ_GPT_OSS_120B,
            output="Hallucinatory contradictory answer",
            latency_ms=150.0,  # faster latency
            token_count=40,
        ),
    ]

    # Model A: lower speed, but 0.0 hallucination
    # Model B: higher speed, but 0.90 severe hallucination
    scores = [
        EvalScoreSchema(
            model_id=ModelID.GEMINI_3_5_FLASH,
            bert_score_f1=0.85,
            rouge_l=0.80,
            hallucination_score=0.05,
            latency_ms=200.0,
            token_count=40,
        ),
        EvalScoreSchema(
            model_id=ModelID.GROQ_GPT_OSS_120B,
            bert_score_f1=0.85,
            rouge_l=0.80,
            hallucination_score=0.90,  # heavily penalized
            latency_ms=150.0,
            token_count=40,
        ),
    ]

    winner = determine_winner(responses, scores)
    assert winner == ModelID.GEMINI_3_5_FLASH
