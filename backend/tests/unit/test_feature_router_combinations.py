"""Unit tests covering exhaustive FeatureFlag combinations and metric routing behavior."""

import itertools

import pytest

from backend.middleware.feature_router import FeatureRouter
from backend.schemas.consumers import (
    EvalConsumerConfig,
    FeatureFlag,
    ScoringMetric,
    TaskType,
)
from backend.schemas.models import ModelID


@pytest.mark.parametrize(
    "flags",
    [
        [],
        [FeatureFlag.BASIC_SCORING],
        [FeatureFlag.OBSERVABILITY],
        [FeatureFlag.LLM_AS_JUDGE],
        [FeatureFlag.RAG_EVAL],
        [FeatureFlag.HALLUCINATION_DETECTION],
        [FeatureFlag.BASIC_SCORING, FeatureFlag.OBSERVABILITY],
        [FeatureFlag.BASIC_SCORING, FeatureFlag.LLM_AS_JUDGE],
        [FeatureFlag.BASIC_SCORING, FeatureFlag.RAG_EVAL, FeatureFlag.HALLUCINATION_DETECTION],
        list(FeatureFlag),
    ],
)
def test_feature_router_flag_combinations(flags: list[FeatureFlag]):
    """Verify FeatureRouter correctly enables and isolates features across flag combinations."""
    config = EvalConsumerConfig(
        consumer_id="test-suite",
        features=flags,
        models=[ModelID.GEMINI_3_5_FLASH],
        task_type=TaskType.QUESTION_ANSWERING,
        scoring_metrics=[
            ScoringMetric.BERT_SCORE,
            ScoringMetric.ROUGE_L,
            ScoringMetric.LATENCY,
            ScoringMetric.TOKEN_COUNT,
            ScoringMetric.ESTIMATED_COST,
            ScoringMetric.LLM_JUDGE,
            ScoringMetric.HALLUCINATION_SCORE,
        ],
    )
    router = FeatureRouter(config)

    # Basic scoring gates BERTScore and ROUGE-L (when reference output provided)
    if FeatureFlag.BASIC_SCORING in flags:
        assert router.should_score_bert("Ground truth reference") is True
        assert router.should_score_rouge("Ground truth reference") is True
    else:
        assert router.should_score_bert("") is False

    # Observability
    if FeatureFlag.OBSERVABILITY in flags:
        assert router.should_trace_observability() is True
    else:
        assert router.should_trace_observability() is False

    # LLM-as-judge
    if FeatureFlag.LLM_AS_JUDGE in flags:
        assert router.should_judge_llm() is True
    else:
        assert router.should_judge_llm() is False

    # RAG eval
    if FeatureFlag.RAG_EVAL in flags:
        assert router.should_evaluate_rag() is True
    else:
        assert router.should_evaluate_rag() is False

    # Hallucination detection
    if FeatureFlag.HALLUCINATION_DETECTION in flags:
        assert router.should_detect_hallucination() is True
    else:
        assert router.should_detect_hallucination() is False

    # Telemetry metrics
    assert router.should_compute_latency() is True
    assert router.should_compute_token_count() is True
    assert router.should_calculate_cost() is True


def test_feature_router_powerset_integrity():
    """Verify that every flag subset can be processed and produces consistent active metrics."""
    all_flags = list(FeatureFlag)
    for r in range(len(all_flags) + 1):
        for combo in itertools.combinations(all_flags, r):
            config = EvalConsumerConfig(
                consumer_id="powerset-test",
                features=list(combo),
                models=[ModelID.GEMINI_3_5_FLASH],
                task_type=TaskType.SUMMARIZATION,
                scoring_metrics=list(ScoringMetric),
            )
            router = FeatureRouter(config)
            metrics = router.get_active_metrics(reference_output="Sample reference text")
            assert isinstance(metrics, list)
            # Basic telemetry metrics are always active when in config
            assert ScoringMetric.LATENCY in metrics
            assert ScoringMetric.TOKEN_COUNT in metrics
            assert ScoringMetric.ESTIMATED_COST in metrics

            # Gated checks
            if FeatureFlag.LLM_AS_JUDGE in combo:
                assert ScoringMetric.LLM_JUDGE in metrics
            else:
                assert ScoringMetric.LLM_JUDGE not in metrics

            if FeatureFlag.HALLUCINATION_DETECTION in combo:
                assert ScoringMetric.HALLUCINATION_SCORE in metrics
            else:
                assert ScoringMetric.HALLUCINATION_SCORE not in metrics
