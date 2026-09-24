"""Redis asynchronous client and pub/sub utilities for caching and real-time streaming.

Operates strictly on Redis DB 0 per ADR-003.
"""

import logging
from uuid import UUID

import redis.asyncio as aioredis

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Global async redis connection pool / client
_redis_client: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis:
    """Get or initialize the global async Redis client instance for DB 0."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_cache_url,
            encoding="utf-8",
            decode_responses=True,
            health_check_interval=30,
        )
    return _redis_client


async def close_redis() -> None:
    """Close the global Redis client connection cleanly."""
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception as exc:
            logger.warning(f"Error closing Redis client: {exc}")
        finally:
            _redis_client = None


async def check_redis_health() -> bool:
    """Ping Redis to verify active connectivity."""
    try:
        client = get_redis_client()
        return bool(await client.ping())
    except Exception as exc:
        logger.warning(f"Redis health check failed: {exc}")
        return False


# Canonical key and channel namespace generators
def run_token_channel(run_id: str | UUID, model_id: str) -> str:
    """Redis pub/sub channel for streaming tokens of a specific model run."""
    return f"run:{run_id}:{model_id}"


def run_status_channel(run_id: str | UUID) -> str:
    """Redis pub/sub channel for global run lifecycle updates."""
    return f"run:{run_id}:status"


def auth_apikey_cache_key(key_hash: str) -> str:
    """Redis cache key for consumer API key lookups."""
    return f"auth:apikey:{key_hash}"


def leaderboard_cache_key(task_type: str) -> str:
    """Redis cache key for leaderboard summaries."""
    return f"cache:leaderboard:{task_type}"
