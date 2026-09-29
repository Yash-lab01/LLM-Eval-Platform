"""Pydantic v2 schemas for Hallucination Detection & sentence-level NLI scoring."""

from pydantic import BaseModel, ConfigDict, Field


class SentenceHallucinationDetail(BaseModel):
    """Evaluation breakdown for an individual sentence statement."""

    model_config = ConfigDict(str_strip_whitespace=True)

    sentence: str = Field(description="Sentence statement analyzed")
    risk_score: float = Field(
        ge=0.0, le=1.0, description="Hallucination risk score (0.0 = grounded, 1.0 = contradictory)"
    )
    label: str = Field(
        description="Classification label: 'grounded', 'unverified', or 'contradiction'"
    )


class HallucinationAnalysisRequest(BaseModel):
    """Payload to analyze candidate model output against reference context."""

    model_config = ConfigDict(str_strip_whitespace=True)

    candidate_text: str = Field(
        min_length=1, max_length=50000, description="Generated model response text"
    )
    reference_text: str = Field(
        min_length=1, max_length=50000, description="Ground truth reference or source context"
    )


class HallucinationAnalysisResult(BaseModel):
    """Full sentence-level hallucination risk assessment."""

    model_config = ConfigDict(from_attributes=True)

    overall_hallucination_score: float = Field(
        ge=0.0, le=1.0, description="Aggregate hallucination risk probability (0.0 to 1.0)"
    )
    is_hallucinating: bool = Field(
        description="Whether candidate output exceeds hallucination threshold (>= 0.40)"
    )
    total_sentences: int = Field(ge=0, description="Total sentences evaluated")
    flagged_sentences: int = Field(
        ge=0, description="Count of ungrounded or contradictory sentences"
    )
    sentences: list[SentenceHallucinationDetail] = Field(default_factory=list)
