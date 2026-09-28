"""Unit tests for chaos failure injection, transient retry backoff, and partial model error resilience."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import litellm
import pytest

from backend.models.eval import ModelResponseORM
from backend.schemas.eval import PromptRunRequest
from backend.schemas.models import ModelID
from backend.services.eval_runner import run_parallel_eval
from backend.services.litellm_client import stream_model_completion


@pytest.mark.asyncio
async def test_rate_limit_retry_exponential_backoff():
    """Verify stream_model_completion retries on RateLimitError with exponential backoff."""
    attempt_counter = 0

    class MockStreamResponse:
        def __init__(self):
            chunk = MagicMock()
            chunk.choices = [
                MagicMock(delta=MagicMock(content="Success after retry"), finish_reason="stop")
            ]
            self._chunks = [chunk]

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self._chunks:
                raise StopAsyncIteration
            return self._chunks.pop(0)

    async def mock_acompletion(*args, **kwargs):
        nonlocal attempt_counter
        attempt_counter += 1
        if attempt_counter < 3:
            raise litellm.RateLimitError(
                message="Rate limit exceeded",
                llm_provider="groq",
                model="groq/openai/gpt-oss-120b",
            )
        return MockStreamResponse()

    with (
        patch("litellm.acompletion", side_effect=mock_acompletion),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        chunks = []
        async for chunk in stream_model_completion(
            run_id="test_run",
            model_id="groq/openai/gpt-oss-120b",
            prompt="Hello",
            max_retries=3,
            initial_backoff=0.05,
        ):
            chunks.append(chunk)

        assert attempt_counter == 3
        # Should have slept twice (attempt 1 -> 0.05, attempt 2 -> 0.10)
        assert mock_sleep.await_count == 2
        final_chunk = [c for c in chunks if c.get("is_final")][0]
        assert final_chunk["attempt_number"] == 3
        assert "Success after retry" in final_chunk["output"]


@pytest.mark.asyncio
async def test_rate_limit_exceeds_max_retries():
    """Verify that transient errors raise exception when max_retries are exhausted."""

    async def mock_acompletion_fail(*args, **kwargs):
        raise litellm.RateLimitError(
            message="Persistent rate limit",
            llm_provider="google",
            model="gemini/gemini-3.5-flash",
        )

    with (
        patch("litellm.acompletion", side_effect=mock_acompletion_fail),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        with pytest.raises(litellm.RateLimitError):
            async for _ in stream_model_completion(
                run_id="test_run",
                model_id="gemini/gemini-3.5-flash",
                prompt="Hello",
                max_retries=2,
                initial_backoff=0.01,
            ):
                pass


@pytest.mark.asyncio
async def test_partial_model_timeout_resilience():
    """Verify that if one model fails/times out, other models complete and the run finishes."""
    run_id = uuid.uuid4()
    request = PromptRunRequest(
        prompt="Tell me about Python",
        models=[ModelID.GEMINI_3_5_FLASH, ModelID.OLLAMA_LLAMA_3_2],
    )

    gemini_resp = {
        "model_id": ModelID.GEMINI_3_5_FLASH,
        "output": "Python is a versatile programming language.",
        "latency_ms": 150.0,
        "token_count": 8,
        "finish_reason": "stop",
        "attempt_number": 1,
    }

    async def mock_stream_and_publish(run_id, model_id, prompt, metadata):
        if model_id == ModelID.OLLAMA_LLAMA_3_2:
            raise TimeoutError("Ollama daemon unreachable on port 11434")
        return gemini_resp

    from datetime import UTC, datetime

    mock_db = AsyncMock()
    mock_run_orm = MagicMock()
    mock_run_orm.created_at = datetime.now(UTC)
    mock_exec_res = MagicMock()
    mock_exec_res.scalar_one.return_value = mock_run_orm
    mock_db.execute = AsyncMock(return_value=mock_exec_res)
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    with (
        patch(
            "backend.services.eval_runner._stream_and_publish_model",
            side_effect=mock_stream_and_publish,
        ),
        patch(
            "backend.services.eval_runner.score_run_responses", new_callable=AsyncMock
        ) as mock_score,
        patch("backend.services.eval_runner.get_redis_client") as mock_redis_getter,
        patch("backend.services.eval_runner.invalidate_leaderboard_cache", new_callable=AsyncMock),
    ):
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock()
        mock_redis_getter.return_value = mock_redis
        mock_score.return_value = ([], None)

        result = await run_parallel_eval(run_id=run_id, request=request, session=mock_db)

        # Run status should complete rather than crash
        assert result.status == "completed"
        # Gemini succeeded, so responses list has 1 item
        assert len(result.responses) == 1
        assert result.responses[0].model_id == ModelID.GEMINI_3_5_FLASH

        # Verify mock_db.add was called for BOTH responses (including partial error ORM response)
        assert mock_db.add.call_count == 2
        added_orms = [call.args[0] for call in mock_db.add.call_args_list]
        models_added = [orm.model_id for orm in added_orms if isinstance(orm, ModelResponseORM)]
        assert ModelID.GEMINI_3_5_FLASH.value in models_added
        assert ModelID.OLLAMA_LLAMA_3_2.value in models_added

        # Verify error message on failed model
        failed_orm = [orm for orm in added_orms if orm.model_id == ModelID.OLLAMA_LLAMA_3_2.value][
            0
        ]
        assert failed_orm.finish_reason == "error"
        assert "Ollama daemon unreachable" in failed_orm.output
