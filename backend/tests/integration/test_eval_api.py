"""Integration tests for evaluation REST endpoints and health checks."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.database import get_db
from backend.main import app
from backend.models.eval import EvalRun
from backend.schemas.consumers import TaskType


@pytest.mark.asyncio
async def test_health_endpoint_components():
    """Verify GET /health returns component statuses for DB and Redis."""
    with (
        patch("backend.main.check_db_health", new_callable=AsyncMock) as mock_db,
        patch("backend.main.check_redis_health", new_callable=AsyncMock) as mock_redis,
    ):
        mock_db.return_value = True
        mock_redis.return_value = True

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["components"]["database"] == "connected"
        assert data["components"]["redis"] == "connected"


@pytest.mark.asyncio
async def test_post_eval_run_endpoint():
    """Verify POST /api/v1/eval/run initializes run record and returns 202."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        with (
            patch("backend.api.routes.eval.run_eval_task.delay") as mock_celery,
            patch(
                "backend.api.routes.eval.run_parallel_eval", new_callable=AsyncMock
            ) as mock_run_parallel,
        ):
            mock_celery.side_effect = Exception("Celery offline in test")

            payload = {
                "prompt": "Write a python function to compute factorial.",
                "models": ["gemini/gemini-3.5-flash", "groq/openai/gpt-oss-20b"],
                "task_type": "code_generation",
                "scoring_metrics": ["latency", "token_count"],
            }

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/v1/eval/run", json=payload)

            assert resp.status_code == 202
            data = resp.json()
            assert "run_id" in data
            assert data["status"] == "pending"
            assert data["task_type"] == "code_generation"
            assert len(data["models"]) == 2
            assert data["stream_url"].startswith("/ws/eval/")
            assert mock_session.add.called
            assert mock_session.commit.called
            assert mock_run_parallel is not None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_eval_run_not_found():
    """Verify GET /api/v1/eval/{run_id} returns 404 for unknown runs."""
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        unknown_id = uuid.uuid4()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/v1/eval/{unknown_id}")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_eval_history_list():
    """Verify GET /api/v1/eval/history/list returns summaries."""
    mock_session = AsyncMock()
    mock_run = EvalRun(
        id=uuid.uuid4(),
        consumer_id=None,
        prompt_text="Test prompt",
        task_type=TaskType.QUESTION_ANSWERING.value,
        models=["gemini/gemini-3.5-flash"],
        status="completed",
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [mock_run]
    mock_session.execute.return_value = mock_res

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/eval/history/list")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["run_id"] == str(mock_run.id)
        assert data[0]["task_type"] == "question_answering"
    finally:
        app.dependency_overrides.clear()
