"""Feature Middleware Layer.

Acts as the single architectural decision point (ADR-002) determining which
evaluation, scoring, and observability features execute based on consumer configuration.
"""

import logging

from backend.schemas.consumers import (
    EvalConsumerConfig,
    FeatureFlag,
    ScoringMetric,
    TaskType,
)
from backend.schemas.models import ModelID

logger = logging.getLogger(__name__)


class FeatureRouter:
    """Evaluates consumer feature declarations and gates pipeline steps."""

    def __init__(self, config: EvalConsumerConfig | None = None) -> None:
        """Initialize router with consumer config or sensible platform defaults."""
        if config is None:
            # Default configuration for direct/unregistered calls
            self.config = EvalConsumerConfig(
                consumer_id="default-consumer",
                features=[FeatureFlag.BASIC_SCORING, FeatureFlag.OBSERVABILITY],
                models=[ModelID.GEMINI_3_5_FLASH],
                task_type=TaskType.QUESTION_ANSWERING,
                scoring_metrics=[
                    ScoringMetric.BERT_SCORE,
                    ScoringMetric.ROUGE_L,
                    ScoringMetric.LATENCY,
                    ScoringMetric.TOKEN_COUNT,
                    ScoringMetric.ESTIMATED_COST,
                ],
            )
        else:
            self.config = config

    @property
    def features(self) -> set[FeatureFlag]:
        """Set of enabled feature flags."""
        return set(self.config.features)

    @property
    def scoring_metrics(self) -> set[ScoringMetric]:
        """Set of requested scoring metrics."""
        return set(self.config.scoring_metrics)

    def should_score_bert(self, reference_output: str | None = None) -> bool:
        """Determine if BERTScore semantic similarity should run."""
        if not reference_output or not reference_output.strip():
            return False
        return (
            FeatureFlag.BASIC_SCORING in self.features
            or ScoringMetric.BERT_SCORE in self.scoring_metrics
        )

    def should_score_rouge(self, reference_output: str | None = None) -> bool:
        """Determine if ROUGE-L n-gram overlap score should run."""
        if not reference_output or not reference_output.strip():
            return False
        return (
            FeatureFlag.BASIC_SCORING in self.features
            or ScoringMetric.ROUGE_L in self.scoring_metrics
        )

    def should_compute_latency(self) -> bool:
        """Determine if latency tracking is active."""
        return (
            FeatureFlag.BASIC_SCORING in self.features
            or ScoringMetric.LATENCY in self.scoring_metrics
        )

    def should_compute_token_count(self) -> bool:
        """Determine if token volume calculation is active."""
        return (
            FeatureFlag.BASIC_SCORING in self.features
            or ScoringMetric.TOKEN_COUNT in self.scoring_metrics
        )

    def should_calculate_cost(self) -> bool:
        """Determine if estimated cost tracking is active."""
        return (
            FeatureFlag.BASIC_SCORING in self.features
            or ScoringMetric.ESTIMATED_COST in self.scoring_metrics
        )

    def should_trace_observability(self) -> bool:
        """Determine if calls should route through Langfuse/observability hooks."""
        return FeatureFlag.OBSERVABILITY in self.features

    def should_judge_llm(self) -> bool:
        """Determine if LLM-as-judge scoring should execute."""
        return FeatureFlag.LLM_AS_JUDGE in self.features

    def should_evaluate_rag(self) -> bool:
        """Determine if RAG retrieval & faithfulness metrics should execute."""
        return FeatureFlag.RAG_EVAL in self.features

    def should_detect_hallucination(self) -> bool:
        """Determine if NLI hallucination detection should execute."""
        return FeatureFlag.HALLUCINATION_DETECTION in self.features

    def get_active_metrics(self, reference_output: str | None = None) -> list[ScoringMetric]:
        """Resolve and return list of all active scoring metrics for this run."""
        active: list[ScoringMetric] = []
        if self.should_score_bert(reference_output):
            active.append(ScoringMetric.BERT_SCORE)
        if self.should_score_rouge(reference_output):
            active.append(ScoringMetric.ROUGE_L)
        if self.should_compute_latency():
            active.append(ScoringMetric.LATENCY)
        if self.should_compute_token_count():
            active.append(ScoringMetric.TOKEN_COUNT)
        if self.should_calculate_cost():
            active.append(ScoringMetric.ESTIMATED_COST)
        if self.should_judge_llm():
            active.append(ScoringMetric.LLM_JUDGE)
        if self.should_detect_hallucination():
            active.append(ScoringMetric.HALLUCINATION_SCORE)
        return active
