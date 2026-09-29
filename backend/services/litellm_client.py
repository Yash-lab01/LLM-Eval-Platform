"""LiteLLM asynchronous client wrapper with streaming, telemetry, and exponential backoff retry.

Enforces ADR-001 (LiteLLM as sole provider gateway) and handles Gemini, Groq, and Ollama.
"""

import asyncio
import logging
import os
import time
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

import litellm

from backend.core.config import settings
from backend.schemas.eval import ModelResponseSchema
from backend.schemas.models import ModelID
from backend.services.observability import setup_observability

logger = logging.getLogger(__name__)

# Configure provider keys in environment for LiteLLM
if settings.gemini_api_key:
    os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
if settings.groq_api_key:
    os.environ["GROQ_API_KEY"] = settings.groq_api_key

# Initialize Langfuse telemetry if credentials present
setup_observability()

# Disable verbose telemetry in production
litellm.set_verbose = settings.environment == "development"


async def stream_model_completion(
    run_id: str,
    model_id: str,
    prompt: str,
    metadata: dict[str, Any] | None = None,
    max_retries: int = 3,
    initial_backoff: float = 1.0,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream model tokens asynchronously with exponential backoff on rate limits and timeouts.

    Yields intermediate token chunks:
        {"token": str, "is_final": False}
    Yields final metadata chunk on completion:
        {"output": str, "latency_ms": float, "token_count": int, "finish_reason": str, "is_final": True}
    """
    messages = [{"role": "user", "content": prompt}]
    meta = metadata or {}
    meta.update({"run_id": run_id, "model_id": model_id})

    attempt = 0
    start_time = time.perf_counter()
    full_text: list[str] = []
    finish_reason = "stop"

    while attempt < max_retries:
        attempt += 1
        try:
            response = await litellm.acompletion(
                model=model_id,
                messages=messages,
                stream=True,
                metadata=meta,
            )

            async for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                content = delta.content if delta and delta.content else ""
                if chunk.choices and chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason

                if content:
                    full_text.append(content)
                    yield {
                        "token": content,
                        "is_final": False,
                    }

            # Completed stream successfully
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            combined_text = "".join(full_text)

            # Calculate token count (fallback to character approximation if usage missing)
            try:
                tokens = litellm.token_counter(model=model_id, text=combined_text)
            except Exception:
                tokens = max(1, len(combined_text) // 4)

            yield {
                "output": combined_text,
                "latency_ms": round(latency_ms, 2),
                "token_count": tokens,
                "finish_reason": finish_reason,
                "attempt_number": attempt,
                "is_final": True,
            }
            return

        except (litellm.RateLimitError, litellm.Timeout) as exc:
            logger.warning(
                f"Transient error calling {model_id} (attempt {attempt}/{max_retries}): {exc}"
            )
            if attempt >= max_retries:
                raise
            backoff_delay = initial_backoff * (2 ** (attempt - 1))
            await asyncio.sleep(backoff_delay)
        except Exception as exc:
            logger.error(f"Unrecoverable error calling {model_id}: {exc}")
            raise


async def generate_model_response(
    model_id: str | ModelID,
    prompt: str,
    metadata: dict[str, Any] | None = None,
) -> ModelResponseSchema:
    """Non-streaming generation helper returning a validated ModelResponseSchema."""
    m_id = model_id.value if hasattr(model_id, "value") else str(model_id)
    run_id = str(uuid4())
    final_chunk: dict[str, Any] | None = None

    async for chunk in stream_model_completion(
        run_id=run_id, model_id=m_id, prompt=prompt, metadata=metadata
    ):
        if chunk.get("is_final"):
            final_chunk = chunk
            break

    if not final_chunk:
        return ModelResponseSchema(
            model_id=ModelID(m_id),
            output="",
            latency_ms=0.0,
            token_count=0,
            finish_reason="error",
        )

    return ModelResponseSchema(
        model_id=ModelID(m_id),
        output=final_chunk["output"],
        latency_ms=final_chunk["latency_ms"],
        token_count=final_chunk["token_count"],
        finish_reason=final_chunk.get("finish_reason", "stop"),
        attempt_number=final_chunk.get("attempt_number", 1),
    )
