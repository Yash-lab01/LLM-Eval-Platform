"""Integration tests for GET /api/v1/eval/compare REST endpoint."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.database import get_db
from backend.main import app
from backend.models.eval import EvalRun, EvalScoreORM


@pytest.mark.asyncio
async def test_compare_runs_endpoint_success():
    """Verify GET /api/v1/eval/compare returns 200 with RunComparison schema."""
    run_id_a = uuid.uuid4()
    run_id_b = uuid.uuid4()

    run_a = EvalRun(
        id=run_id_a,
        prompt_text="Prompt A",
        task_type="question_answering",
        models=["gemini/gemini-3.5-flash"],
        status="completed",
        created_at=datetime.now(UTC),
    )
    run_a.scores = [
        EvalScoreORM(
            id=uuid.uuid4(),
            run_id=run_id_a,
            model_id="gemini/gemini-3.5-flash",
            bert_score_f1=0.85,
            rouge_l=0.80,
            latency_ms=200.0,
            token_count=50,
            estimated_cost_usd=0.0001,
        )
    ]

    run_b = EvalRun(
        id=run_id_b,
        prompt_text="Prompt B",
        task_type="question_answering",
        models=["gemini/gemini-3.5-flash"],
        status="completed",
        created_at=datetime.now(UTC),
    )
    run_b.scores = [
        EvalScoreORM(
            id=uuid.uuid4(),
            run_id=run_id_b,
            model_id="gemini/gemini-3.5-flash",
            bert_score_f1=0.90,
            rouge_l=0.85,
            latency_ms=180.0,
            token_count=55,
            estimated_cost_usd=0.00011,
        )
    ]

    mock_session = AsyncMock()
    mock_res_a = MagicMock()
    mock_res_a.scalar_one_or_none.return_value = run_a
    mock_res_b = MagicMock()
    mock_res_b.scalar_one_or_none.return_value = run_b
    mock_session.execute.side_effect = [mock_res_a, mock_res_b]

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/eval/compare",
                params={"run_id_a": str(run_id_a), "run_id_b": str(run_id_b)},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id_a"] == str(run_id_a)
        assert data["run_id_b"] == str(run_id_b)
        assert "gemini/gemini-3.5-flash" in data["score_deltas"]
        assert data["score_deltas"]["gemini/gemini-3.5-flash"]["bert_score_f1"] == 0.05
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_compare_runs_endpoint_not_found():
    """Verify GET /api/v1/eval/compare returns 404 if a run does not exist."""
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/eval/compare",
                params={"run_id_a": str(uuid.uuid4()), "run_id_b": str(uuid.uuid4())},
            )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()
