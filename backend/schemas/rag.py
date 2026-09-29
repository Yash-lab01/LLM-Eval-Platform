"""Pydantic v2 schemas for RAG (Retrieval-Augmented Generation) pipeline evaluation."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.models import ModelID


class RAGScoreSchema(BaseModel):
    """Tripartite scoring metrics for RAG pipeline evaluation."""

    model_config = ConfigDict(from_attributes=True)

    context_relevance: float = Field(
        ge=0.0,
        le=1.0,
        description="Relevance of retrieved context chunks to user query (0.0 to 1.0)",
    )
    faithfulness: float = Field(
        ge=0.0,
        le=1.0,
        description="Factual grounding of answer in retrieved context (1.0 - hallucination)",
    )
    answer_relevance: float = Field(
        ge=0.0,
        le=1.0,
        description="Relevance of generated answer to original user query (0.0 to 1.0)",
    )
    composite_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Weighted composite score: 0.3*context + 0.4*faithfulness + 0.3*answer",
    )


class RAGRunRequest(BaseModel):
    """Payload to evaluate models on a RAG task with retrieved contexts."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=50000, description="Original user query/question")
    contexts: list[str] = Field(
        min_length=1,
        max_length=50,
        description="Retrieved context document chunks or passages",
    )
    models: list[ModelID] = Field(
        min_length=1, max_length=10, description="Candidate models to benchmark"
    )
    consumer_id: str | None = Field(default=None, description="Optional caller consumer ID")


class RAGModelResult(BaseModel):
    """Evaluation result for an individual model on a RAG task."""

    model_config = ConfigDict(from_attributes=True)

    model_id: ModelID
    answer: str
    latency_ms: float = Field(ge=0.0)
    token_count: int = Field(ge=0)
    scores: RAGScoreSchema


class RAGRunResult(BaseModel):
    """Complete summary of a multi-model RAG evaluation run."""

    model_config = ConfigDict(from_attributes=True)

    run_id: UUID = Field(default_factory=uuid4)
    query: str
    contexts: list[str]
    results: list[RAGModelResult] = Field(default_factory=list)
    winner: ModelID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
