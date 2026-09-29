"""Unit tests for RAG pipeline evaluation metrics and multi-model benchmark runner."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.schemas.eval import ModelResponseSchema
from backend.schemas.models import ModelID
from backend.schemas.rag import RAGRunRequest
from backend.services.rag_eval import (
    compute_answer_relevance,
    compute_context_relevance,
    compute_faithfulness,
    evaluate_rag_metrics,
    run_rag_evaluation,
)


@pytest.mark.asyncio
async def test_context_relevance_matching():
    """Verify context relevance is high when contexts contain key query terms."""
    query = "What is the boiling point of water at sea level?"
    relevant_contexts = [
        "Water boils at 100 degrees Celsius (212 degrees Fahrenheit) at standard atmospheric pressure at sea level.",
        "Atmospheric pressure influences the boiling point of liquids.",
    ]
    score = await compute_context_relevance(query, relevant_contexts)
    assert score >= 0.70

    irrelevant_contexts = ["Bananas are rich in potassium and grown in tropical climates."]
    score_low = await compute_context_relevance(query, irrelevant_contexts)
    assert score_low <= 0.30


@pytest.mark.asyncio
async def test_faithfulness_grounding():
    """Verify faithfulness is high when answer strictly reflects retrieved context facts."""
    contexts = [
        "The Hubble Space Telescope was launched into low Earth orbit in 1990 and remains in operation.",
        "It was named after astronomer Edwin Hubble.",
    ]

    faithful_answer = "The Hubble Space Telescope was launched in 1990 into low Earth orbit."
    faith_score = await compute_faithfulness(faithful_answer, contexts)
    assert faith_score >= 0.70

    unfaithful_answer = (
        "Hubble was launched in 1950 by the Russian space agency and operates on Mars."
    )
    unfaith_score = await compute_faithfulness(unfaithful_answer, contexts)
    assert unfaith_score < faith_score


@pytest.mark.asyncio
async def test_answer_relevance():
    """Verify answer relevance measures alignment between question and response."""
    query = "What is machine learning?"
    relevant_answer = (
        "Machine learning is a subfield of artificial intelligence focused on learning from data."
    )
    score = await compute_answer_relevance(query, relevant_answer)
    assert score > 0.0

    empty_score = await compute_answer_relevance("", "")
    assert empty_score == 0.0


@pytest.mark.asyncio
async def test_evaluate_rag_metrics_composite():
    """Verify tripartite RAG metrics compute proper composite score."""
    query = "How does photosynthesis work?"
    contexts = [
        "Photosynthesis is used by plants to convert light energy into chemical energy.",
        "Chlorophyll absorbs light to synthesize glucose from water and carbon dioxide.",
    ]
    answer = (
        "Plants use chlorophyll to convert light energy, carbon dioxide, and water into glucose."
    )

    scores = await evaluate_rag_metrics(query, contexts, answer)
    assert 0.0 <= scores.context_relevance <= 1.0
    assert 0.0 <= scores.faithfulness <= 1.0
    assert 0.0 <= scores.answer_relevance <= 1.0
    assert 0.0 <= scores.composite_score <= 1.0


@pytest.mark.asyncio
async def test_run_rag_evaluation_runner():
    """Verify run_rag_evaluation generates and benchmarks models on RAG tasks."""
    mock_response = ModelResponseSchema(
        model_id=ModelID.GEMINI_3_5_FLASH,
        output="The James Webb Telescope was launched on December 25, 2021.",
        latency_ms=180.0,
        token_count=35,
    )

    with patch(
        "backend.services.rag_eval.generate_model_response",
        AsyncMock(return_value=mock_response),
    ):
        request = RAGRunRequest(
            query="When was JWST launched?",
            contexts=["The James Webb Space Telescope (JWST) was launched on December 25, 2021."],
            models=[ModelID.GEMINI_3_5_FLASH],
        )

        result = await run_rag_evaluation(request)
        assert result.query == "When was JWST launched?"
        assert len(result.results) == 1
        assert result.winner == ModelID.GEMINI_3_5_FLASH
        assert result.results[0].scores.faithfulness >= 0.70
