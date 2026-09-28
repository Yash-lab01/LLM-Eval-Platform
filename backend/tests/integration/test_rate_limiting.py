"""Integration tests for SlowAPI rate limiting and payload size limits."""

import json
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.schemas.models import ModelID


@pytest.mark.asyncio
async def test_prompt_size_limit_validation():
    """Verify prompts exceeding 50,000 characters are rejected with 422 Unprocessable Entity."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        huge_prompt = "A" * 50001
        payload = {
            "prompt": huge_prompt,
            "models": [ModelID.GEMINI_3_5_FLASH.value],
        }
        response = await client.post("/api/v1/eval/run", json=payload)
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("prompt" in str(err) for err in errors)


@pytest.mark.asyncio
async def test_reference_output_size_limit_validation():
    """Verify reference outputs exceeding 50,000 characters are rejected with 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        huge_reference = "B" * 50001
        payload = {
            "prompt": "Explain quantum computing",
            "models": [ModelID.GEMINI_3_5_FLASH.value],
            "scoring_metrics": ["bert_score"],
            "reference_output": huge_reference,
        }
        response = await client.post("/api/v1/eval/run", json=payload)
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_rate_limiting_trigger_429():
    """Verify that exceeding rate limits returns HTTP 429 with custom JSON error."""
    from backend.core.limiter import limiter

    with patch.object(limiter._limiter, "hit", return_value=False):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/v1/leaderboard")
            assert res.status_code == 429
            data = res.json()
            assert data["error"] == "Rate limit exceeded"
            assert "Retry-After" in res.headers


def test_custom_rate_limit_exceeded_handler():
    """Verify the rate limit custom exception handler formatting."""
    from starlette.requests import Request

    from backend.core.limiter import rate_limit_exceeded_handler

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/eval/run",
        "headers": [],
    }
    request = Request(scope)
    mock_exc = MagicMock()
    mock_exc.detail = "20 per 1 minute"
    mock_exc.retry_after = 60

    response = rate_limit_exceeded_handler(request, mock_exc)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    data = json.loads(response.body.decode())
    assert data["error"] == "Rate limit exceeded"
    assert "20 per 1 minute" in data["detail"]
