"""Integration tests for Celery task dispatch and eager execution."""

import uuid
from unittest.mock import AsyncMock, patch

from backend.core.celery_app import celery_app
from backend.schemas.eval import EvalRunResult, ModelResponseSchema
from backend.schemas.models import ModelID
from backend.tasks.eval_tasks import run_eval_task


def test_run_eval_task_eager_execution():
    """Verify run_eval_task executes cleanly in eager mode and returns result dict."""
    # Enable eager execution for synchronous in-process test
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)

    run_id = uuid.uuid4()
    request_data = {
        "prompt": "Evaluate this test prompt",
        "models": [ModelID.GEMINI_3_5_FLASH.value],
    }

    from datetime import UTC, datetime

    mock_result = EvalRunResult(
        run_id=run_id,
        prompt="Evaluate this test prompt",
        task_type="question_answering",
        models=[ModelID.GEMINI_3_5_FLASH],
        status="completed",
        created_at=datetime.now(UTC),
        responses=[
            ModelResponseSchema(
                model_id=ModelID.GEMINI_3_5_FLASH,
                output="Test generation",
                latency_ms=120.0,
                token_count=10,
            )
        ],
        scores=[],
        winner=None,
    )

    with patch("backend.tasks.eval_tasks.run_parallel_eval", new_callable=AsyncMock) as mock_eval:
        mock_eval.return_value = mock_result

        async_res = run_eval_task.delay(str(run_id), request_data)

        assert async_res.successful()
        result = async_res.result
        assert result["run_id"] == str(run_id)
        assert result["status"] == "completed"
        assert result["responses_count"] == 1
        mock_eval.assert_awaited_once()


def test_run_eval_task_retry_configuration():
    """Verify Celery task has retry backoff, max retries, and correct queue defined."""
    assert run_eval_task.max_retries == 3
    assert run_eval_task.retry_backoff is True
    assert run_eval_task.queue == "eval_default"
