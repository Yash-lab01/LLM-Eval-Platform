"""Authentication dependency validating consumer API keys with Redis caching."""

import hashlib
import json
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.redis_client import auth_apikey_cache_key, get_redis_client
from backend.models.consumer import Consumer

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_api_key(api_key: str) -> str:
    """Compute deterministic SHA-256 hash of API key for caching and lookups."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


async def get_current_consumer(
    api_key: Annotated[str | None, Security(API_KEY_HEADER)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> Consumer | None:
    """Validate consumer API key against Redis cache, falling back to PostgreSQL."""
    if not api_key:
        if settings.environment == "development":
            # In local development, allow unauthenticated access defaulting to first consumer if available
            return None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required X-API-Key header",
        )

    key_hash = hash_api_key(api_key)
    redis_key = auth_apikey_cache_key(key_hash)

    # 1. Attempt Redis cache lookup
    try:
        redis_client = get_redis_client()
        cached_data = await redis_client.get(redis_key)
        if cached_data:
            consumer_dict = json.loads(cached_data)
            # Fetch fresh model instance from DB by cached ID
            stmt = select(Consumer).where(Consumer.id == consumer_dict["id"])
            consumer = (await db.execute(stmt)).scalar_one_or_none()
            if consumer:
                return consumer
    except Exception as exc:
        logger.debug(f"Redis API key cache lookup failed: {exc}")

    # 2. Database lookup
    stmt = select(Consumer).where(Consumer.api_key == api_key)
    consumer = (await db.execute(stmt)).scalar_one_or_none()

    if not consumer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key provided",
        )

    # 3. Populate Redis cache (1 hour TTL)
    try:
        redis_client = get_redis_client()
        cache_payload = json.dumps(
            {
                "id": str(consumer.id),
                "name": consumer.name,
            }
        )
        await redis_client.set(redis_key, cache_payload, ex=3600)
    except Exception as exc:
        logger.debug(f"Failed to populate Redis API key cache: {exc}")

    return consumer
