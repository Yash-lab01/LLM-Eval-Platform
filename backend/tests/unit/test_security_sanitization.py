"""Unit tests for security hardening, API key hashing, authentication caching, and data sanitization."""

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.api.middleware.auth import get_current_consumer, hash_api_key
from backend.core.config import settings
from backend.models.consumer import Consumer
from backend.services.observability import build_trace_metadata


def test_env_files_in_gitignore():
    """Verify .env files are strictly excluded in .gitignore to prevent secret leaks."""
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    gitignore_path = root_dir / ".gitignore"

    assert gitignore_path.exists(), ".gitignore must exist in root repository"
    content = gitignore_path.read_text(encoding="utf-8")
    lines = [
        line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")
    ]

    assert ".env" in lines, ".env must be explicitly ignored"
    assert any(".env" in line for line in lines)


def test_hash_api_key_sha256():
    """Verify hash_api_key computes standard 64-char hexadecimal SHA-256 hash."""
    sample_key = "test_consumer_secret_api_key_999"
    key_hash = hash_api_key(sample_key)

    assert len(key_hash) == 64
    # Deterministic test
    assert key_hash == hash_api_key(sample_key)
    # Different keys produce different hashes
    assert key_hash != hash_api_key(sample_key + "x")


@pytest.mark.asyncio
async def test_auth_missing_key_in_production():
    """Verify missing API key raises HTTP 401 in production environment."""
    with patch.object(settings, "environment", "production"):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_consumer(api_key=None, db=AsyncMock())
        assert exc_info.value.status_code == 401
        assert "Missing required X-API-Key" in exc_info.value.detail


@pytest.mark.asyncio
async def test_auth_missing_key_in_development():
    """Verify missing API key is permitted in development environment."""
    with patch.object(settings, "environment", "development"):
        consumer = await get_current_consumer(api_key=None, db=AsyncMock())
        assert consumer is None


@pytest.mark.asyncio
async def test_auth_valid_key_db_lookup_and_cache_population():
    """Verify valid API key resolves from DB and caches into Redis with 1h TTL."""
    consumer_id = uuid.uuid4()
    mock_consumer = Consumer(
        id=consumer_id,
        name="Alpha Corp",
        api_key="alpha_live_secret_key",
        config={},
    )

    mock_db = AsyncMock()
    mock_db_res = MagicMock()
    mock_db_res.scalar_one_or_none.return_value = mock_consumer
    mock_db.execute.return_value = mock_db_res

    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()

    with patch("backend.api.middleware.auth.get_redis_client", return_value=mock_redis):
        consumer = await get_current_consumer(api_key="alpha_live_secret_key", db=mock_db)

        assert consumer is not None
        assert consumer.name == "Alpha Corp"
        assert consumer.id == consumer_id
        # Verify cached in Redis with ex=3600
        mock_redis.set.assert_awaited_once()
        args, kwargs = mock_redis.set.call_args
        assert kwargs.get("ex") == 3600


@pytest.mark.asyncio
async def test_auth_valid_key_redis_cache_hit():
    """Verify valid API key resolves directly from Redis cache."""
    consumer_id = uuid.uuid4()
    mock_consumer = Consumer(
        id=consumer_id,
        name="Cached Corp",
        api_key="cached_live_secret_key",
        config={},
    )

    cached_payload = json.dumps(
        {
            "id": str(consumer_id),
            "name": "Cached Corp",
            "features": [],
        }
    )

    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=cached_payload)

    mock_db = AsyncMock()
    mock_db_res = MagicMock()
    mock_db_res.scalar_one_or_none.return_value = mock_consumer
    mock_db.execute.return_value = mock_db_res

    with patch("backend.api.middleware.auth.get_redis_client", return_value=mock_redis):
        consumer = await get_current_consumer(api_key="cached_live_secret_key", db=mock_db)

        assert consumer is not None
        assert consumer.id == consumer_id
        mock_redis.get.assert_awaited_once()


def test_trace_metadata_sanitization():
    """Verify trace metadata contains session context without leaking sensitive API credentials."""
    run_id = uuid.uuid4()
    metadata = build_trace_metadata(
        run_id=run_id,
        model_id="gemini/gemini-3.5-flash",
        task_type="summarization",
        consumer_id="consumer_42",
    )

    assert metadata["session_id"] == "consumer_42"
    assert metadata["trace_user_id"] == "consumer_42"
    assert metadata["task_type"] == "summarization"
    assert metadata["model_id"] == "gemini/gemini-3.5-flash"
    assert "api_key" not in metadata
    assert "secret" not in metadata
