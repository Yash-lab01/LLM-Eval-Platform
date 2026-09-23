"""Unit tests for Pydantic v2 schemas and validation logic."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.schemas.consumers import (
    ConsumerCreate,
    EvalConsumerConfig,
    FeatureFlag,
    ScoringMetric,
    TaskType,
)
from backend.schemas.eval import (
    EvalScoreSchema,
    ModelResponseSchema,
    PromptRunRequest,
)
from backend.schemas.leaderboard import LeaderboardEntry, ModelRecommendation
from backend.schemas.models import (
    ModelID,
    ModelProvider,
    get_model_provider,
)
from backend.schemas.prompts import PromptCreate


def test_model_id_enum_and_provider_resolution():
    """Verify ModelID enum values and provider derivation."""
    assert ModelID.GEMINI_3_5_FLASH.value == "gemini/gemini-3.5-flash"
    assert get_model_provider(ModelID.GEMINI_3_5_FLASH) == ModelProvider.GOOGLE

    assert ModelID.GROQ_GPT_OSS_120B.value == "groq/openai/gpt-oss-120b"
    assert get_model_provider(ModelID.GROQ_GPT_OSS_120B) == ModelProvider.GROQ

    assert ModelID.OLLAMA_LLAMA_3_2.value == "ollama/llama3.2"
    assert get_model_provider(ModelID.OLLAMA_LLAMA_3_2) == ModelProvider.OLLAMA


def test_eval_consumer_config_valid():
    """Verify valid EvalConsumerConfig construction and defaults."""
    config = EvalConsumerConfig(
        consumer_id="ai-terminal-agent",
        features=[FeatureFlag.BASIC_SCORING, FeatureFlag.OBSERVABILITY],
        models=[ModelID.GEMINI_3_5_FLASH, ModelID.GROQ_QWEN_27B],
        task_type=TaskType.COMMAND_GENERATION,
        scoring_metrics=[ScoringMetric.LATENCY, ScoringMetric.TOKEN_COUNT],
    )
    assert config.consumer_id == "ai-terminal-agent"
    assert len(config.models) == 2
    assert FeatureFlag.OBSERVABILITY in config.features


def test_eval_consumer_config_invalid_consumer_id():
    """Verify consumer_id enforces kebab-case regex."""
    with pytest.raises(ValidationError):
        EvalConsumerConfig(
            consumer_id="Invalid_CamelCase_Name!",
            models=[ModelID.GEMINI_3_5_FLASH],
        )


def test_eval_consumer_config_model_count_constraints():
    """Verify models field rejects empty lists."""
    with pytest.raises(ValidationError):
        EvalConsumerConfig(
            consumer_id="valid-id",
            models=[],
        )


def test_prompt_run_request_valid_with_reference():
    """Verify PromptRunRequest succeeds when reference_output provided for BERTScore."""
    req = PromptRunRequest(
        prompt="Explain asyncpg pooling.",
        models=[ModelID.GROQ_GPT_OSS_20B],
        task_type=TaskType.QUESTION_ANSWERING,
        scoring_metrics=[ScoringMetric.BERT_SCORE, ScoringMetric.LATENCY],
        reference_output="Connection pooling caches open connections for reuse.",
    )
    assert req.reference_output is not None
    assert ScoringMetric.BERT_SCORE in req.scoring_metrics


def test_prompt_run_request_bert_score_requires_reference():
    """Verify PromptRunRequest raises ValueError when BERTScore requested without reference_output."""
    with pytest.raises(ValidationError) as exc_info:
        PromptRunRequest(
            prompt="Explain asyncpg pooling.",
            models=[ModelID.GROQ_GPT_OSS_20B],
            task_type=TaskType.QUESTION_ANSWERING,
            scoring_metrics=[ScoringMetric.BERT_SCORE],
            reference_output=None,
        )
    assert "reference_output is required when BERT_SCORE or ROUGE_L is evaluated" in str(
        exc_info.value
    )


def test_prompt_run_request_rouge_l_requires_reference():
    """Verify PromptRunRequest raises ValueError when ROUGE_L requested without reference_output."""
    with pytest.raises(ValidationError) as exc_info:
        PromptRunRequest(
            prompt="Explain asyncpg pooling.",
            models=[ModelID.GROQ_GPT_OSS_20B],
            scoring_metrics=[ScoringMetric.ROUGE_L],
            reference_output="",
        )
    assert "reference_output is required when BERT_SCORE or ROUGE_L is evaluated" in str(
        exc_info.value
    )


def test_model_response_schema():
    """Verify ModelResponseSchema serialization and constraints."""
    resp = ModelResponseSchema(
        model_id=ModelID.GEMINI_3_8_FLASH,
        output="Hello world",
        latency_ms=152.4,
        token_count=45,
        finish_reason="stop",
    )
    dumped = resp.model_dump()
    assert dumped["model_id"] == "gemini/gemini-3.8-flash"
    assert dumped["latency_ms"] == 152.4
    assert dumped["from_cache"] is False


def test_eval_score_schema_bounds():
    """Verify EvalScoreSchema validates score ranges."""
    score = EvalScoreSchema(
        model_id=ModelID.GROQ_QWEN_32B,
        bert_score_f1=0.895,
        rouge_l=0.742,
        latency_ms=210.0,
        token_count=120,
        estimated_cost_usd=0.00015,
    )
    assert score.bert_score_f1 == 0.895

    # Out of range BERTScore (> 1.0) must fail
    with pytest.raises(ValidationError):
        EvalScoreSchema(
            model_id=ModelID.GROQ_QWEN_32B,
            bert_score_f1=1.5,
            latency_ms=100.0,
            token_count=50,
        )


def test_leaderboard_and_recommendation_schemas():
    """Verify LeaderboardEntry and ModelRecommendation models."""
    entry = LeaderboardEntry(
        model_id=ModelID.GEMINI_3_5_FLASH,
        task_type=TaskType.CODE_GENERATION,
        total_runs=25,
        win_rate=80.0,
        avg_bert_score=0.92,
        avg_latency_ms=310.5,
        avg_token_count=180.0,
        total_estimated_cost_usd=0.005,
    )
    assert entry.win_rate == 80.0

    rec = ModelRecommendation(
        task_type=TaskType.CODE_GENERATION,
        recommended_model=ModelID.GEMINI_3_5_FLASH,
        metric=ScoringMetric.BERT_SCORE,
        score=0.92,
        reason="Highest average BERTScore F1 on code generation tasks",
    )
    assert rec.recommended_model == ModelID.GEMINI_3_5_FLASH


def test_orm_to_pydantic_from_attributes():
    """Verify Pydantic models can ingest ORM-like attribute objects."""

    class MockConsumerORM:
        id = uuid.uuid4()
        name = "Research Agent"
        api_key = "test_key_abc_123"
        config = {
            "consumer_id": "research-agent",
            "features": ["basic_scoring"],
            "models": ["gemini/gemini-3.5-flash"],
            "task_type": "question_answering",
            "scoring_metrics": ["latency"],
        }
        created_at = datetime.now(UTC)

    # ConsumerCreate validation
    payload = ConsumerCreate(
        name="Research Agent",
        config=EvalConsumerConfig(
            consumer_id="research-agent",
            models=[ModelID.GEMINI_3_5_FLASH],
        ),
    )
    assert payload.name == "Research Agent"

    # PromptCreate
    prompt = PromptCreate(
        content="Test prompt content",
        task_type=TaskType.SUMMARIZATION,
        tags=["nlp"],
    )
    assert prompt.task_type == TaskType.SUMMARIZATION
