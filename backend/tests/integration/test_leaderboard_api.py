"""Integration tests for Leaderboard and Recommendation REST endpoints and caching."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.database import get_db
from backend.main import app
from backend.schemas.consumers import TaskType
from backend.schemas.leaderboard import LeaderboardEntry, LeaderboardResponse
from backend.schemas.models import ModelID
from backend.services.leaderboard import invalidate_leaderboard_cache


@pytest.mark.asyncio
async def test_get_leaderboard_endpoint_empty():
    """Verify GET /api/v1/leaderboard returns 200 with empty list when no runs exist."""
    mock_session = AsyncMock()
    # Mock empty query results
    mock_wins = MagicMock()
    mock_wins.all.return_value = []
    mock_stats = MagicMock()
    mock_stats.all.return_value = []
    mock_session.execute.side_effect = [mock_wins, mock_stats]

    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        with patch("backend.services.leaderboard.get_redis_client") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = None  # Cache miss
            mock_get_redis.return_value = mock_redis

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/leaderboard")

            assert resp.status_code == 200
            data = resp.json()
            assert data["entries"] == []
            assert data["from_cache"] is False
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_leaderboard_redis_cache_hit():
    """Verify leaderboard endpoint returns cached payload with from_cache=True."""
    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    cached_json = (
        '{"task_type": "question_answering", "from_cache": false, '
        '"cached_at": "2026-09-24T12:00:00Z", '
        '"entries": [{"model_id": "gemini/gemini-3.5-flash", "task_type": "question_answering", '
        '"total_runs": 10, "win_rate": 80.0, "avg_bert_score": 0.91, "avg_rouge_l": 0.85, '
        '"avg_latency_ms": 190.5, "avg_token_count": 45.0, "total_estimated_cost_usd": 0.0015}]}'
    )

    try:
        with patch("backend.services.leaderboard.get_redis_client") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = cached_json
            mock_get_redis.return_value = mock_redis

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/leaderboard", params={"task_type": "question_answering"}
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["from_cache"] is True
            assert len(data["entries"]) == 1
            assert data["entries"][0]["model_id"] == "gemini/gemini-3.5-flash"
            assert data["entries"][0]["win_rate"] == 80.0
            # Database should not have been queried
            assert not mock_session.execute.called
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_leaderboard_force_refresh_bypasses_cache():
    """Verify force_refresh=true bypasses Redis cache and queries DB."""
    mock_session = AsyncMock()
    mock_wins = MagicMock()
    mock_wins.all.return_value = []
    mock_stats = MagicMock()
    mock_stats.all.return_value = []
    mock_session.execute.side_effect = [mock_wins, mock_stats]

    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        with patch("backend.services.leaderboard.get_redis_client") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = '{"entries": []}'
            mock_get_redis.return_value = mock_redis

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/leaderboard", params={"force_refresh": "true"})

            assert resp.status_code == 200
            data = resp.json()
            assert data["from_cache"] is False
            assert mock_session.execute.called
            # Set cache was called
            assert mock_redis.set.called
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_model_recommendation_default_fallback():
    """Verify model recommendation falls back gracefully when no benchmark data exists."""
    mock_session = AsyncMock()
    mock_wins = MagicMock()
    mock_wins.all.return_value = []
    mock_stats = MagicMock()
    mock_stats.all.return_value = []
    mock_session.execute.side_effect = [mock_wins, mock_stats]

    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        with patch("backend.services.leaderboard.get_redis_client") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = None
            mock_get_redis.return_value = mock_redis

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/models/recommend",
                    params={"task_type": "code_generation", "metric": "latency"},
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["task_type"] == "code_generation"
            assert data["recommended_model"] == ModelID.GEMINI_3_5_FLASH.value
            assert (
                "insufficient" in data["reason"].lower() or "defaulting" in data["reason"].lower()
            )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_model_recommendation_metric_selection():
    """Verify model recommendation selects top model according to chosen metric."""
    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    fake_leaderboard = LeaderboardResponse(
        task_type=TaskType.QUESTION_ANSWERING,
        entries=[
            LeaderboardEntry(
                model_id=ModelID.GEMINI_3_5_FLASH,
                task_type=TaskType.QUESTION_ANSWERING,
                total_runs=20,
                win_rate=60.0,
                avg_bert_score=0.88,
                avg_rouge_l=0.80,
                avg_latency_ms=300.0,
                avg_token_count=50.0,
                total_estimated_cost_usd=0.003,
            ),
            LeaderboardEntry(
                model_id=ModelID.GROQ_GPT_OSS_20B,
                task_type=TaskType.QUESTION_ANSWERING,
                total_runs=20,
                win_rate=40.0,
                avg_bert_score=0.75,
                avg_rouge_l=0.70,
                avg_latency_ms=90.0,
                avg_token_count=40.0,
                total_estimated_cost_usd=0.001,
            ),
        ],
        from_cache=False,
    )

    try:
        with patch(
            "backend.services.leaderboard.get_leaderboard_data",
            new_callable=AsyncMock,
            return_value=fake_leaderboard,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # 1. Recommendation for lowest latency
                resp_latency = await client.get(
                    "/api/v1/models/recommend",
                    params={"task_type": "question_answering", "metric": "latency"},
                )
                assert resp_latency.status_code == 200
                assert resp_latency.json()["recommended_model"] == ModelID.GROQ_GPT_OSS_20B.value

                # 2. Recommendation for highest bert_score
                resp_bert = await client.get(
                    "/api/v1/models/recommend",
                    params={"task_type": "question_answering", "metric": "bert_score"},
                )
                assert resp_bert.status_code == 200
                assert resp_bert.json()["recommended_model"] == ModelID.GEMINI_3_5_FLASH.value
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_invalidate_leaderboard_cache():
    """Verify cache invalidation deletes keys for given task type and all."""
    mock_redis = AsyncMock()
    with patch("backend.services.leaderboard.get_redis_client", return_value=mock_redis):
        await invalidate_leaderboard_cache(TaskType.QUESTION_ANSWERING)
        assert mock_redis.delete.called
        deleted_args = mock_redis.delete.call_args[0]
        assert "cache:leaderboard:all" in deleted_args
        assert "cache:leaderboard:question_answering" in deleted_args
