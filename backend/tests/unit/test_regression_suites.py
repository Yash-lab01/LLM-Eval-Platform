"""Unit tests for Regression Testing prompt suites and delta comparison reports."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from backend.schemas.consumers import TaskType
from backend.schemas.eval import EvalRunResult, EvalScoreSchema, ModelResponseSchema
from backend.schemas.models import ModelID
from backend.schemas.suite import PromptSuiteCreate, SuitePromptItem
from backend.services.suite_service import (
    generate_regression_report,
    get_prompt_suite,
    list_prompt_suites,
    list_suite_runs,
    run_prompt_suite,
    save_prompt_suite,
)


@pytest.mark.asyncio
async def test_suite_creation_and_retrieval():
    """Verify benchmark prompt suites can be saved, fetched, and listed."""
    create = PromptSuiteCreate(
        name="Core Reasoning Benchmark",
        description="Complex logical deduction prompts",
        task_type=TaskType.QUESTION_ANSWERING,
        prompts=[
            SuitePromptItem(id="p1", prompt="Prompt 1", reference_output="Answer 1"),
            SuitePromptItem(id="p2", prompt="Prompt 2", reference_output="Answer 2"),
        ],
    )

    suite = await save_prompt_suite(create)
    assert suite.name == "Core Reasoning Benchmark"
    assert len(suite.prompts) == 2

    fetched = await get_prompt_suite(suite.id)
    assert fetched is not None
    assert fetched.id == suite.id
    assert fetched.name == "Core Reasoning Benchmark"

    all_suites = await list_prompt_suites()
    assert any(s.id == suite.id for s in all_suites)


@pytest.mark.asyncio
async def test_suite_execution_and_regression_report():
    """Verify running a suite twice and generating a regression report with score deltas."""
    create = PromptSuiteCreate(
        name="Regression Test Suite",
        description="Evaluates improvement when switching models",
        task_type=TaskType.QUESTION_ANSWERING,
        prompts=[
            SuitePromptItem(id="q1", prompt="Query 1", reference_output="Ref 1"),
            SuitePromptItem(id="q2", prompt="Query 2", reference_output="Ref 2"),
        ],
    )
    suite = await save_prompt_suite(create)

    # 1. Baseline run (lower scores)
    baseline_eval = EvalRunResult(
        run_id=uuid4(),
        prompt="Query",
        task_type=TaskType.QUESTION_ANSWERING,
        models=[ModelID.GEMINI_3_5_FLASH],
        status="completed",
        responses=[
            ModelResponseSchema(
                model_id=ModelID.GEMINI_3_5_FLASH,
                output="Base output",
                latency_ms=300.0,
                token_count=50,
            )
        ],
        scores=[
            EvalScoreSchema(
                model_id=ModelID.GEMINI_3_5_FLASH,
                bert_score_f1=0.70,
                rouge_l=0.65,
                llm_judge_score=0.68,
                latency_ms=300.0,
                token_count=50,
            )
        ],
        winner=ModelID.GEMINI_3_5_FLASH,
        created_at=suite.created_at,
    )

    with patch(
        "backend.services.suite_service.run_parallel_eval", AsyncMock(return_value=baseline_eval)
    ):
        base_record = await run_prompt_suite(suite.id, models=[ModelID.GEMINI_3_5_FLASH])
        assert base_record.suite_id == suite.id
        assert len(base_record.item_scores) == 2

    # 2. Candidate run (higher scores = improved)
    candidate_eval = EvalRunResult(
        run_id=uuid4(),
        prompt="Query",
        task_type=TaskType.QUESTION_ANSWERING,
        models=[ModelID.GEMINI_3_5_FLASH],
        status="completed",
        responses=[
            ModelResponseSchema(
                model_id=ModelID.GEMINI_3_5_FLASH,
                output="Candidate improved output",
                latency_ms=200.0,
                token_count=45,
            )
        ],
        scores=[
            EvalScoreSchema(
                model_id=ModelID.GEMINI_3_5_FLASH,
                bert_score_f1=0.85,
                rouge_l=0.80,
                llm_judge_score=0.88,
                latency_ms=200.0,
                token_count=45,
            )
        ],
        winner=ModelID.GEMINI_3_5_FLASH,
        created_at=suite.created_at,
    )

    with patch(
        "backend.services.suite_service.run_parallel_eval", AsyncMock(return_value=candidate_eval)
    ):
        cand_record = await run_prompt_suite(suite.id, models=[ModelID.GEMINI_3_5_FLASH])
        assert cand_record.suite_id == suite.id

    runs = await list_suite_runs(suite.id)
    assert len(runs) >= 2

    # 3. Generate regression report
    report = await generate_regression_report(
        suite_id=suite.id,
        baseline_run_id=base_record.run_id,
        candidate_run_id=cand_record.run_id,
    )

    assert report.suite_id == suite.id
    assert report.baseline_run_id == base_record.run_id
    assert report.candidate_run_id == cand_record.run_id
    assert report.total_prompts == 2
    assert report.improved_count == 2
    assert report.degraded_count == 0
    assert report.net_quality_delta > 0.0

    # Verify per-prompt metric deltas
    delta_item = report.deltas[0]
    assert delta_item.status == "improved"
    assert "bert_score_f1" in delta_item.metrics
    assert delta_item.metrics["bert_score_f1"].delta == 0.15
    assert delta_item.metrics["rouge_l"].delta == 0.15
