"""Integration tests for Phase 7C REST APIs: Visualizer, HTML/PDF Reports, and Webhook Alerts."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.database import get_db
from backend.main import app
from backend.models.eval import EvalRun, EvalScoreORM, ModelResponseORM


@pytest.fixture
def sample_db_run():
    """Create sample populated EvalRun ORM object."""
    run_id = uuid4()
    run = EvalRun(
        id=run_id,
        prompt_text="Explain Python generators",
        task_type="question_answering",
        models=["gemini/gemini-3.5-flash", "groq/openai/gpt-oss-120b"],
        status="completed",
        reference_output="Generators use yield to lazily produce values.",
        created_at=datetime.now(UTC),
    )
    run.responses = [
        ModelResponseORM(
            id=uuid4(),
            run_id=run_id,
            model_id="gemini/gemini-3.5-flash",
            output="Generators are functions that yield values on demand.",
            latency_ms=180.0,
            token_count=35,
            finish_reason="stop",
        ),
        ModelResponseORM(
            id=uuid4(),
            run_id=run_id,
            model_id="groq/openai/gpt-oss-120b",
            output="A generator function yields items lazily.",
            latency_ms=210.0,
            token_count=30,
            finish_reason="stop",
        ),
    ]
    run.scores = [
        EvalScoreORM(
            id=uuid4(),
            run_id=run_id,
            model_id="gemini/gemini-3.5-flash",
            bert_score_f1=0.88,
            rouge_l=0.82,
            latency_ms=180.0,
            token_count=35,
        ),
        EvalScoreORM(
            id=uuid4(),
            run_id=run_id,
            model_id="groq/openai/gpt-oss-120b",
            bert_score_f1=0.80,
            rouge_l=0.78,
            latency_ms=210.0,
            token_count=30,
        ),
    ]
    return run


@pytest.mark.asyncio
async def test_custom_visualizer_endpoint():
    """Verify POST /api/v1/visualizer/embeddings generates 2D points and similarity matrix."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "prompt": "What is Docker?",
            "reference_output": "Docker packages software into containers.",
            "candidate_responses": {
                "gemini/gemini-3.5-flash": "Docker provides containerized application packaging.",
                "groq/openai/gpt-oss-120b": "Containers package apps with system dependencies.",
            },
        }
        resp = await ac.post("/api/v1/visualizer/embeddings", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "points" in data
        assert len(data["points"]) == 4  # prompt, reference, 2 candidates
        assert "similarity_matrix" in data
        assert "method" in data


@pytest.mark.asyncio
async def test_run_visualizer_and_export_endpoints(sample_db_run):
    """Verify /eval/{id}/visualizer and /eval/{id}/export/html endpoints."""
    mock_db = AsyncMock()
    mock_scalar = MagicMock()
    mock_scalar.scalar_one_or_none.return_value = sample_db_run
    mock_db.execute.return_value = mock_scalar

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            run_id = str(sample_db_run.id)

            # 1. Visualizer for run
            vis_resp = await ac.get(f"/api/v1/eval/{run_id}/visualizer")
            assert vis_resp.status_code == 200
            vis_data = vis_resp.json()
            assert len(vis_data["points"]) >= 3

            # 2. HTML report export
            html_resp = await ac.get(f"/api/v1/eval/{run_id}/export/html")
            assert html_resp.status_code == 200
            assert "text/html" in html_resp.headers.get("content-type", "")
            assert "<!DOCTYPE html>" in html_resp.text
            assert "Explain Python generators" in html_resp.text

            # 3. PDF report export
            pdf_resp = await ac.get(f"/api/v1/eval/{run_id}/export/pdf")
            assert pdf_resp.status_code == 200
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_webhooks_api_endpoints():
    """Verify webhook check and test dispatch endpoints."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Check thresholds
        check_payload = {
            "run_id": str(uuid4()),
            "scores": [
                {
                    "model_id": "gemini/gemini-3.5-flash",
                    "latency_ms": 5200.0,  # exceeds 4000.0
                    "token_count": 50,
                    "hallucination_score": 0.55,  # exceeds 0.40
                }
            ],
            "config": {
                "url": "https://example.com/webhook",
                "hallucination_threshold": 0.40,
                "latency_threshold_ms": 4000.0,
            },
        }
        with patch(
            "backend.services.webhook_service.dispatch_webhook_alert", AsyncMock(return_value=True)
        ):
            check_resp = await ac.post("/api/v1/webhooks/check", json=check_payload)
            assert check_resp.status_code == 200
            check_data = check_resp.json()
            assert check_data["alerts_triggered_count"] == 2

        # 2. Test webhook delivery with mock
        with patch(
            "backend.api.routes.webhooks.dispatch_webhook_alert", AsyncMock(return_value=True)
        ):
            test_resp = await ac.post(
                "/api/v1/webhooks/test",
                json={"target_url": "https://example.com/alerts"},
            )
            assert test_resp.status_code == 200
            assert test_resp.json()["status"] == "delivered"
