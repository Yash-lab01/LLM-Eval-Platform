"""Integration tests for FastMCP Server tools."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.eval import EvalRun
from backend.schemas.consumers import ScoringMetric, TaskType
from backend.schemas.eval import (
    EvalRunResult,
    ModelResponseSchema,
    RunComparison,
)
from backend.schemas.leaderboard import ModelRecommendation
from backend.schemas.models import ModelID
from mcp.eval_server import (
    compare_runs,
    get_best_model,
    get_eval_history,
    health_check,
    run_eval,
)


@pytest.mark.asyncio
async def test_mcp_health_check():
    """Verify MCP health_check tool returns healthy status."""
    res = await health_check()
    assert res["status"] == "healthy"
    assert "llm-eval-mcp-server" in res["service"]


@pytest.mark.asyncio
async def test_mcp_get_best_model():
    """Verify MCP get_best_model tool returns ModelRecommendation schema."""
    fake_rec = ModelRecommendation(
        task_type=TaskType.QUESTION_ANSWERING,
        recommended_model=ModelID.GEMINI_3_5_FLASH,
        metric=ScoringMetric.BERT_SCORE,
        score=0.91,
        reason="Highest semantic similarity score across benchmarks",
    )

    with patch("mcp.eval_server.get_model_recommendation", new_callable=AsyncMock) as mock_rec:
        mock_rec.return_value = fake_rec

        rec = await get_best_model(task_type="question_answering", metric="bert_score")
        assert rec.recommended_model == ModelID.GEMINI_3_5_FLASH
        assert rec.score == 0.91


@pytest.mark.asyncio
async def test_mcp_get_eval_history():
    """Verify MCP get_eval_history tool returns list of EvalRunSummary."""
    mock_run = EvalRun(
        id=uuid.uuid4(),
        consumer_id=None,
        prompt_text="Sample prompt",
        task_type=TaskType.SUMMARIZATION.value,
        models=[ModelID.GEMINI_3_5_FLASH.value],
        status="completed",
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )

    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [mock_run]
    mock_session.execute.return_value = mock_res

    with patch("mcp.eval_server.AsyncSessionFactory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session

        history = await get_eval_history(limit=5)
        assert len(history) == 1
        assert history[0].run_id == mock_run.id
        assert history[0].task_type == TaskType.SUMMARIZATION


@pytest.mark.asyncio
async def test_mcp_compare_runs():
    """Verify MCP compare_runs tool delegates to compare_eval_runs."""
    run_id_a = str(uuid.uuid4())
    run_id_b = str(uuid.uuid4())

    fake_comparison = RunComparison(
        run_id_a=uuid.UUID(run_id_a),
        run_id_b=uuid.UUID(run_id_b),
        score_deltas={"gemini/gemini-3.5-flash": {"latency_ms": -30.0}},
    )

    with patch("mcp.eval_server.compare_eval_runs", new_callable=AsyncMock) as mock_comp:
        mock_comp.return_value = fake_comparison

        comp = await compare_runs(run_id_a=run_id_a, run_id_b=run_id_b)
        assert str(comp.run_id_a) == run_id_a
        assert comp.score_deltas["gemini/gemini-3.5-flash"]["latency_ms"] == -30.0


@pytest.mark.asyncio
async def test_mcp_run_eval():
    """Verify MCP run_eval tool executes parallel evaluation and returns EvalRunResult."""
    run_id = uuid.uuid4()
    fake_result = EvalRunResult(
        run_id=run_id,
        prompt="Explain quantum computing simply",
        task_type=TaskType.QUESTION_ANSWERING,
        models=[ModelID.GEMINI_3_5_FLASH],
        status="completed",
        responses=[
            ModelResponseSchema(
                model_id=ModelID.GEMINI_3_5_FLASH,
                output="Quantum computers use qubits instead of regular bits.",
                latency_ms=180.0,
                token_count=35,
                created_at=datetime.now(UTC),
            )
        ],
        scores=[],
        winner=ModelID.GEMINI_3_5_FLASH,
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    with (
        patch("mcp.eval_server.AsyncSessionFactory") as mock_factory,
        patch("mcp.eval_server.run_parallel_eval", new_callable=AsyncMock) as mock_runner,
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_runner.return_value = fake_result

        result = await run_eval(
            prompt="Explain quantum computing simply",
            task_type="question_answering",
            models=["gemini/gemini-3.5-flash"],
        )

        assert result.run_id == run_id
        assert result.status == "completed"
        assert result.winner == ModelID.GEMINI_3_5_FLASH
        assert len(result.responses) == 1
        assert mock_session.add.called
        assert mock_runner.called
