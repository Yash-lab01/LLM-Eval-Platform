"""Integration tests for Phase 7B REST APIs: RAG pipeline eval and Hallucination detection."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.schemas.eval import ModelResponseSchema
from backend.schemas.models import ModelID


@pytest.mark.asyncio
async def test_hallucination_api_endpoint():
    """Verify POST /api/v1/eval/hallucination returns sentence-level analysis."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "candidate_text": "The moon is made of green cheese. Neil Armstrong was the first astronaut on it.",
            "reference_text": "Neil Armstrong walked on the moon in 1969. The moon is composed of rock and dust.",
        }
        resp = await ac.post("/api/v1/eval/hallucination", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_hallucination_score" in data
        assert "is_hallucinating" in data
        assert "sentences" in data
        assert len(data["sentences"]) >= 1


@pytest.mark.asyncio
async def test_rag_metrics_api_endpoint():
    """Verify POST /api/v1/eval/rag/metrics returns tripartite scores."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "query": "What is Python?",
            "contexts": [
                "Python is an interpreted, high-level, general-purpose programming language.",
                "Its design philosophy emphasizes code readability with the use of significant indentation.",
            ],
            "answer": "Python is a high-level programming language emphasizing readability.",
        }
        resp = await ac.post("/api/v1/eval/rag/metrics", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "context_relevance" in data
        assert "faithfulness" in data
        assert "answer_relevance" in data
        assert "composite_score" in data


@pytest.mark.asyncio
async def test_rag_run_api_endpoint():
    """Verify POST /api/v1/eval/rag benchmarks models on RAG task."""
    mock_model_resp = ModelResponseSchema(
        model_id=ModelID.GEMINI_3_5_FLASH,
        output="Linux is an open-source Unix-like operating system kernel.",
        latency_ms=140.0,
        token_count=30,
    )

    with patch(
        "backend.services.rag_eval.generate_model_response",
        AsyncMock(return_value=mock_model_resp),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "query": "What is Linux?",
                "contexts": [
                    "Linux is a family of open-source Unix-like operating systems based on the Linux kernel.",
                    "First released by Linus Torvalds on September 17, 1991.",
                ],
                "models": ["gemini/gemini-3.5-flash"],
            }
            resp = await ac.post("/api/v1/eval/rag", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["query"] == "What is Linux?"
            assert len(data["results"]) == 1
            assert data["winner"] == "gemini/gemini-3.5-flash"
            assert "composite_score" in data["results"][0]["scores"]
