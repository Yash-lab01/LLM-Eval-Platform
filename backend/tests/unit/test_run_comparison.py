"""Unit tests for the Run Comparison service."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.eval import EvalRun, EvalScoreORM
from backend.services.run_comparison import compare_eval_runs


@pytest.mark.asyncio
async def test_compare_eval_runs_computes_deltas():
    """Verify compare_eval_runs computes correct metric deltas across shared models."""
    run_id_a = uuid.uuid4()
    run_id_b = uuid.uuid4()

    # Run A: baseline scores
    score_a = EvalScoreORM(
        id=uuid.uuid4(),
        run_id=run_id_a,
        model_id="gemini/gemini-3.5-flash",
        bert_score_f1=0.80,
        rouge_l=0.75,
        latency_ms=300.0,
        token_count=100,
        estimated_cost_usd=0.00015,
    )
    run_a = EvalRun(
        id=run_id_a,
        prompt_text="Prompt A",
        task_type="question_answering",
        models=["gemini/gemini-3.5-flash"],
        status="completed",
        created_at=datetime.now(UTC),
    )
    run_a.scores = [score_a]

    # Run B: improved scores
    score_b = EvalScoreORM(
        id=uuid.uuid4(),
        run_id=run_id_b,
        model_id="gemini/gemini-3.5-flash",
        bert_score_f1=0.88,
        rouge_l=0.82,
        latency_ms=250.0,
        token_count=90,
        estimated_cost_usd=0.000135,
    )
    run_b = EvalRun(
        id=run_id_b,
        prompt_text="Prompt B",
        task_type="question_answering",
        models=["gemini/gemini-3.5-flash"],
        status="completed",
        created_at=datetime.now(UTC),
    )
    run_b.scores = [score_b]

    mock_session = AsyncMock()
    mock_res_a = MagicMock()
    mock_res_a.scalar_one_or_none.return_value = run_a
    mock_res_b = MagicMock()
    mock_res_b.scalar_one_or_none.return_value = run_b
    mock_session.execute.side_effect = [mock_res_a, mock_res_b]

    comparison = await compare_eval_runs(run_id_a=run_id_a, run_id_b=run_id_b, session=mock_session)

    assert comparison.run_id_a == run_id_a
    assert comparison.run_id_b == run_id_b
    assert "gemini/gemini-3.5-flash" in comparison.score_deltas

    deltas = comparison.score_deltas["gemini/gemini-3.5-flash"]
    # 0.88 - 0.80 = +0.08
    assert deltas["bert_score_f1"] == 0.08
    # 0.82 - 0.75 = +0.07
    assert deltas["rouge_l"] == 0.07
    # 250.0 - 300.0 = -50.0ms (latency reduction)
    assert deltas["latency_ms"] == -50.0
    # 90 - 100 = -10 tokens
    assert deltas["token_count"] == -10.0


@pytest.mark.asyncio
async def test_compare_eval_runs_missing_run_raises():
    """Verify compare_eval_runs raises ValueError if a requested run ID is not found."""
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res

    with pytest.raises(ValueError, match="not found"):
        await compare_eval_runs(
            run_id_a=uuid.uuid4(),
            run_id_b=uuid.uuid4(),
            session=mock_session,
        )
