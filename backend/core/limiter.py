"""Rate limiting infrastructure for the LLM Evaluation Platform.

Uses slowapi with custom key resolution (API Key header or client IP)
and automatic in-memory fallback for testing or Redis unavailability.
"""

import os
import sys

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from backend.core.config import settings


def get_rate_limit_key(request: Request) -> str:
    """Resolve rate limit bucket key from X-API-Key header or remote IP."""
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"apikey:{api_key}"
    return get_remote_address(request) or "127.0.0.1"


# Detect test runtime or offline Redis environment
is_test_env = (
    settings.environment == "test" or "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ
)

storage_uri = "memory://" if is_test_env else settings.redis_cache_url

limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["120/minute"],
    storage_uri=storage_uri,
    in_memory_fallback_enabled=True,
    swallow_errors=True,
    strategy="fixed-window",
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Custom JSON response handler for rate limit exceeded errors."""
    detail = getattr(exc, "detail", str(exc))
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": f"Too many requests: {detail}",
            "retry_after": getattr(exc, "retry_after", None),
        },
        headers={"Retry-After": str(getattr(exc, "retry_after", 60))},
    )
