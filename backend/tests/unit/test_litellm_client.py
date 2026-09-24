"""Unit tests for LiteLLM streaming wrapper and error handling."""

from unittest.mock import AsyncMock, MagicMock, patch

import litellm
import pytest

from backend.services.litellm_client import stream_model_completion


@pytest.mark.asyncio
async def test_stream_model_completion_success():
    """Verify stream_model_completion yields individual tokens and final completion summary."""

    # Mock chunks from litellm.acompletion
    def make_chunk(text, finish=None):
        choice = MagicMock()
        choice.delta.content = text
        choice.finish_reason = finish
        chunk = MagicMock()
        chunk.choices = [choice]
        return chunk

    async def mock_generator():
        yield make_chunk("Hello")
        yield make_chunk(" world")
        yield make_chunk("!", finish="stop")

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.return_value = mock_generator()

        chunks = []
        async for c in stream_model_completion(
            run_id="run-123",
            model_id="gemini/gemini-3.5-flash",
            prompt="Hi",
        ):
            chunks.append(c)

        # Expected 3 token chunks + 1 final chunk
        assert len(chunks) == 4
        assert chunks[0] == {"token": "Hello", "is_final": False}
        assert chunks[1] == {"token": " world", "is_final": False}
        assert chunks[2] == {"token": "!", "is_final": False}

        final_chunk = chunks[3]
        assert final_chunk["is_final"] is True
        assert final_chunk["output"] == "Hello world!"
        assert final_chunk["finish_reason"] == "stop"
        assert final_chunk["latency_ms"] >= 0.0
        assert final_chunk["token_count"] >= 1


@pytest.mark.asyncio
async def test_stream_model_completion_rate_limit_retry():
    """Verify rate limit errors trigger backoff retry and eventually succeed."""

    def make_chunk(text):
        choice = MagicMock()
        choice.delta.content = text
        choice.finish_reason = "stop"
        chunk = MagicMock()
        chunk.choices = [choice]
        return chunk

    async def mock_generator():
        yield make_chunk("Retried successfully")

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
        # First attempt raises RateLimitError, second attempt succeeds
        mock_acompletion.side_effect = [
            litellm.RateLimitError(
                message="Rate limit reached",
                model="groq/openai/gpt-oss-20b",
                llm_provider="groq",
            ),
            mock_generator(),
        ]

        chunks = []
        async for c in stream_model_completion(
            run_id="run-456",
            model_id="groq/openai/gpt-oss-20b",
            prompt="Hi",
            max_retries=2,
            initial_backoff=0.01,
        ):
            chunks.append(c)

        assert mock_acompletion.call_count == 2
        final_chunk = [c for c in chunks if c["is_final"]][0]
        assert final_chunk["output"] == "Retried successfully"
        assert final_chunk["attempt_number"] == 2
