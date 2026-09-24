"""Unit tests for the FeatureRouter middleware layer."""

from backend.middleware.feature_router import FeatureRouter
from backend.schemas.consumers import (
    EvalConsumerConfig,
    FeatureFlag,
    ScoringMetric,
    TaskType,
)
from backend.schemas.models import ModelID


def test_default_feature_router():
    """Verify default router initialization provides baseline metrics."""
    router = FeatureRouter()
    assert router.config.consumer_id == "default-consumer"
    assert FeatureFlag.BASIC_SCORING in router.features
    assert FeatureFlag.OBSERVABILITY in router.features

    # With reference output, basic scoring enables bert and rouge
    assert router.should_score_bert("Expected reference") is True
    assert router.should_score_rouge("Expected reference") is True

    # Without reference output, semantic metrics are disabled
    assert router.should_score_bert(None) is False
    assert router.should_score_bert("") is False
    assert router.should_score_rouge(None) is False

    assert router.should_compute_latency() is True
    assert router.should_compute_token_count() is True
    assert router.should_calculate_cost() is True
    assert router.should_trace_observability() is True

    # Advanced features default to False
    assert router.should_judge_llm() is False
    assert router.should_evaluate_rag() is False
    assert router.should_detect_hallucination() is False


def test_custom_feature_router_gates():
    """Verify custom consumer configuration enables specified features and metrics."""
    config = EvalConsumerConfig(
        consumer_id="custom-consumer",
        features=[
            FeatureFlag.BASIC_SCORING,
            FeatureFlag.LLM_AS_JUDGE,
            FeatureFlag.HALLUCINATION_DETECTION,
        ],
        models=[ModelID.GROQ_GPT_OSS_120B],
        task_type=TaskType.SUMMARIZATION,
        scoring_metrics=[ScoringMetric.BERT_SCORE, ScoringMetric.LLM_JUDGE],
    )
    router = FeatureRouter(config)

    assert router.should_judge_llm() is True
    assert router.should_detect_hallucination() is True
    assert router.should_evaluate_rag() is False
    assert router.should_trace_observability() is False


def test_get_active_metrics_resolution():
    """Verify get_active_metrics produces appropriate metric list based on reference availability."""
    router = FeatureRouter()
    with_ref = router.get_active_metrics("Some reference")
    without_ref = router.get_active_metrics(None)

    assert ScoringMetric.BERT_SCORE in with_ref
    assert ScoringMetric.ROUGE_L in with_ref
    assert ScoringMetric.LATENCY in with_ref

    assert ScoringMetric.BERT_SCORE not in without_ref
    assert ScoringMetric.ROUGE_L not in without_ref
    assert ScoringMetric.LATENCY in without_ref
