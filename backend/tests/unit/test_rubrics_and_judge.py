"""Unit tests for Custom Evaluation Rubrics and LLM-as-Judge engine."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from backend.middleware.feature_router import FeatureRouter
from backend.schemas.consumers import EvalConsumerConfig, FeatureFlag, TaskType
from backend.schemas.eval import ModelResponseSchema
from backend.schemas.models import ModelID
from backend.schemas.rubrics import RubricCriterion, RubricSchema
from backend.services.llm_judge import (
    _clean_json_markdown,
    build_judge_prompt,
    evaluate_with_llm_judge,
)
from backend.services.rubric_service import (
    DEFAULT_RUBRICS,
    get_default_rubric,
    get_rubric_for_task,
    list_all_rubrics,
    save_custom_rubric,
)
from backend.services.scoring import determine_winner, score_run_responses


def test_default_rubrics_present_for_all_tasks():
    """Verify built-in default rubrics exist for all TaskTypes with positive weights."""
    for task_type in TaskType:
        rubric = get_default_rubric(task_type)
        assert rubric.task_type == task_type
        assert len(rubric.criteria) >= 1
        total_weight = sum(c.weight for c in rubric.criteria)
        assert total_weight > 0.0


@pytest.mark.asyncio
async def test_custom_rubric_persistence():
    """Verify custom rubrics can be registered and retrieved."""
    custom = RubricSchema(
        task_type=TaskType.CODE_GENERATION,
        title="Python Clean Architecture Rubric",
        description="Strict SOLID and typing evaluation",
        criteria=[
            RubricCriterion(
                name="type_safety",
                weight=0.5,
                description="Are comprehensive type hints used?",
            ),
            RubricCriterion(
                name="modularity",
                weight=0.5,
                description="Is code split into modular SRP functions?",
            ),
        ],
    )
    saved = await save_custom_rubric(custom)
    assert saved.title == "Python Clean Architecture Rubric"

    retrieved = await get_rubric_for_task(TaskType.CODE_GENERATION)
    assert retrieved.title == "Python Clean Architecture Rubric"
    assert len(retrieved.criteria) == 2

    all_rubrics = await list_all_rubrics()
    assert len(all_rubrics) == len(DEFAULT_RUBRICS)


def test_clean_json_markdown():
    """Verify markdown fences and whitespace are cleanly stripped from LLM JSON outputs."""
    raw_with_fences = '```json\n{"overall_score": 0.88, "reasoning": "Good output"}\n```'
    cleaned = _clean_json_markdown(raw_with_fences)
    assert cleaned == '{"overall_score": 0.88, "reasoning": "Good output"}'

    raw_plain = '{"overall_score": 0.75}'
    assert _clean_json_markdown(raw_plain) == '{"overall_score": 0.75}'

    raw_with_text = 'Here is the score:\n{"overall_score": 0.90}\nHope this helps.'
    assert _clean_json_markdown(raw_with_text) == '{"overall_score": 0.90}'


def test_build_judge_prompt():
    """Verify judge prompt formats rubric criteria and reference outputs properly."""
    rubric = get_default_rubric(TaskType.SUMMARIZATION)
    prompt = build_judge_prompt(
        prompt="Summarize article",
        candidate_output="Candidate summary",
        rubric=rubric,
        reference_output="Ground truth summary",
    )
    assert "Original User Prompt:\nSummarize article" in prompt
    assert "Ground Truth Reference Output:\nGround truth summary" in prompt
    assert "Candidate Model Output to Evaluate:\nCandidate summary" in prompt
    assert "coverage" in prompt


@pytest.mark.asyncio
async def test_evaluate_with_llm_judge_fallback():
    """Verify LLM judge returns valid score even when no external keys exist."""
    score = await evaluate_with_llm_judge(
        prompt="Explain quantum computing",
        candidate_output="Quantum computing uses qubits and superposition.",
        task_type=TaskType.QUESTION_ANSWERING,
    )
    assert 0.0 <= score.overall_score <= 1.0
    assert len(score.criterion_scores) > 0
    assert len(score.reasoning) > 0


@pytest.mark.asyncio
async def test_evaluate_with_llm_judge_mock_response():
    """Verify LLM judge parses LiteLLM response JSON properly."""
    mock_choice = AsyncMock()
    mock_choice.message.content = (
        '{"criterion_scores": {"accuracy": 0.95, "clarity": 0.90, "completeness": 0.85}, '
        '"overall_score": 0.92, "reasoning": "Accurate, well-structured explanation."}'
    )
    mock_litellm_resp = AsyncMock(choices=[mock_choice])

    with (
        patch("backend.services.llm_judge.litellm.acompletion", return_value=mock_litellm_resp),
        patch("backend.core.config.settings.gemini_api_key", "mock-key"),
    ):
        score = await evaluate_with_llm_judge(
            prompt="What is Docker?",
            candidate_output="Docker packages applications into containers.",
            task_type=TaskType.QUESTION_ANSWERING,
        )
        assert score.overall_score == 0.92
        assert score.criterion_scores["accuracy"] == 0.95
        assert "Accurate" in score.reasoning


@pytest.mark.asyncio
async def test_scoring_integration_with_llm_judge():
    """Verify score_run_responses invokes LLM judge when feature flag is active."""
    router = FeatureRouter(
        EvalConsumerConfig(
            consumer_id="judge-test-consumer",
            features=[FeatureFlag.LLM_AS_JUDGE],
            models=[ModelID.GEMINI_3_5_FLASH, ModelID.GROQ_GPT_OSS_120B],
            task_type=TaskType.QUESTION_ANSWERING,
            scoring_metrics=[],
        )
    )

    responses = [
        ModelResponseSchema(
            model_id=ModelID.GEMINI_3_5_FLASH,
            output="Clear, well-reasoned answer.",
            latency_ms=150.0,
            token_count=40,
            finish_reason="stop",
        ),
        ModelResponseSchema(
            model_id=ModelID.GROQ_GPT_OSS_120B,
            output="Another high quality answer.",
            latency_ms=250.0,
            token_count=45,
            finish_reason="stop",
        ),
    ]

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    scores, winner = await score_run_responses(
        run_id=uuid4(),
        task_type=TaskType.QUESTION_ANSWERING,
        reference_output=None,
        responses=responses,
        router=router,
        session=mock_db,
        prompt="Explain photosynthesis",
    )

    assert len(scores) == 2
    for sc in scores:
        assert sc.llm_judge_score is not None
        assert 0.0 <= sc.llm_judge_score <= 1.0
    assert winner in [ModelID.GEMINI_3_5_FLASH, ModelID.GROQ_GPT_OSS_120B]


def test_determine_winner_factors_llm_judge():
    """Verify determine_winner gives victory to the model with higher LLM judge score."""
    from backend.schemas.eval import EvalScoreSchema

    responses = [
        ModelResponseSchema(
            model_id=ModelID.GEMINI_3_5_FLASH,
            output="Response A",
            latency_ms=200.0,
            token_count=50,
        ),
        ModelResponseSchema(
            model_id=ModelID.GROQ_GPT_OSS_120B,
            output="Response B",
            latency_ms=205.0,
            token_count=50,
        ),
    ]

    # Model B has significantly higher LLM judge score despite identical latency
    scores = [
        EvalScoreSchema(
            model_id=ModelID.GEMINI_3_5_FLASH,
            latency_ms=200.0,
            token_count=50,
            llm_judge_score=0.40,
        ),
        EvalScoreSchema(
            model_id=ModelID.GROQ_GPT_OSS_120B,
            latency_ms=205.0,
            token_count=50,
            llm_judge_score=0.95,
        ),
    ]

    winner = determine_winner(responses, scores)
    assert winner == ModelID.GROQ_GPT_OSS_120B
