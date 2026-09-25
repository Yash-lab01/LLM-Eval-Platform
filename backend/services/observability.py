"""LLM Observability and Tracing Service.

Configures Langfuse callback integration into LiteLLM and injects standardized
trace metadata (consumer session, task type, run ID) into model calls.
"""

import logging
import os
from typing import Any
from uuid import UUID

import litellm

from backend.core.config import settings

logger = logging.getLogger(__name__)

_OBSERVABILITY_INITIALIZED = False


def setup_observability() -> bool:
    """Initialize Langfuse telemetry callbacks in LiteLLM if credentials are present.

    Returns True if Langfuse is configured, False if running without telemetry.
    """
    global _OBSERVABILITY_INITIALIZED

    if settings.langfuse_public_key and settings.langfuse_secret_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
        os.environ["LANGFUSE_HOST"] = settings.langfuse_host

        if not hasattr(litellm, "success_callback") or litellm.success_callback is None:
            litellm.success_callback = []
        if not hasattr(litellm, "failure_callback") or litellm.failure_callback is None:
            litellm.failure_callback = []

        if "langfuse" not in litellm.success_callback:
            litellm.success_callback.append("langfuse")
        if "langfuse" not in litellm.failure_callback:
            litellm.failure_callback.append("langfuse")

        _OBSERVABILITY_INITIALIZED = True
        logger.info(f"Langfuse observability initialized (Host: {settings.langfuse_host})")
        return True

    logger.debug("Langfuse API keys not provided; running without external telemetry")
    _OBSERVABILITY_INITIALIZED = False
    return False


def is_observability_active() -> bool:
    """Check if Langfuse telemetry callbacks are active."""
    return _OBSERVABILITY_INITIALIZED


def build_trace_metadata(
    run_id: UUID | str,
    model_id: str,
    task_type: str,
    consumer_id: str | None = None,
    extra_tags: list[str] | None = None,
) -> dict[str, Any]:
    """Construct standardized Langfuse session and trace metadata for LiteLLM calls.

    Maps consumer_id to session_id and trace_user_id to allow session-level grouping
    in the Langfuse dashboard.
    """
    user_session = consumer_id or "anonymous-consumer"
    tags = [task_type]
    if extra_tags:
        tags.extend(extra_tags)

    return {
        "run_id": str(run_id),
        "model_id": model_id,
        "task_type": task_type,
        "session_id": user_session,
        "trace_user_id": user_session,
        "trace_name": f"eval-run-{run_id}",
        "tags": tags,
    }
