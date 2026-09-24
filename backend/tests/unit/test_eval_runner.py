"""Unit tests for the parallel evaluation runner and Redis pub/sub broadcasting."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.eval import EvalRun
from backend.schemas.consumers import TaskType
from backend.schemas.eval import PromptRunRequest
from backend.schemas.models import ModelID
from backend.services.eval_runner import run_parallel_eval


@pytest.mark.asyncio
async def test_run_parallel_eval_executes_models_and_completes():
    """Verify run_parallel_eval gathers model streams and marks run completed."""
    run_id = uuid.uuid4()
    request = PromptRunRequest(
        prompt="Tell me about Python",
        models=[ModelID.GEMINI_3_5_FLASH, ModelID.GROQ_GPT_OSS_20B],
        task_type=TaskType.QUESTION_ANSWERING,
    )

    # Mock stream_model_completion generator
    async def mock_stream(run_id, model_id, prompt, metadata):
        yield {"token": "Generated", "is_final": False}
        yield {
            "output": f"Output from {model_id}",
            "latency_ms": 120.0,
            "token_count": 25,
            "finish_reason": "stop",
            "attempt_number": 1,
            "is_final": True,
        }

    # Mock DB Session
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_run = EvalRun(
        id=run_id,
        prompt_text=request.prompt,
        task_type=request.task_type.value,
        models=[m.value for m in request.models],
        status="running",
        created_at=datetime.now(UTC),
    )
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = mock_run
    mock_session.execute.return_value = mock_result

    # Mock Redis client
    mock_redis = AsyncMock()

    with (
        patch("backend.services.eval_runner.stream_model_completion", side_effect=mock_stream),
        patch("backend.services.eval_runner.get_redis_client", return_value=mock_redis),
    ):
        result = await run_parallel_eval(
            run_id=run_id,
            request=request,
            session=mock_session,
        )

        assert result.status == "completed"
        assert len(result.responses) == 2
        assert result.responses[0].output == "Output from gemini/gemini-3.5-flash"
        assert result.responses[1].output == "Output from groq/openai/gpt-oss-20b"
        assert mock_redis.publish.call_count >= 2  # tokens + status events
        assert mock_session.commit.called
