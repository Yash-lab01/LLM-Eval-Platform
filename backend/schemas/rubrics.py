"""Pydantic v2 schemas for Custom Scoring Rubrics and LLM-as-Judge (G-Eval style) evaluation."""

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.consumers import TaskType


class RubricCriterion(BaseModel):
    """An individual scoring criterion within a rubric."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100, description="Criterion name (e.g. correctness)")
    weight: float = Field(
        default=1.0, ge=0.0, le=10.0, description="Relative weight in overall score"
    )
    description: str = Field(
        min_length=1, max_length=500, description="Detailed grading guidance for judge"
    )


class RubricSchema(BaseModel):
    """A collection of criteria defining evaluation rubrics for a specific task category."""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_type: TaskType = Field(description="Task category this rubric applies to")
    title: str = Field(min_length=1, max_length=150, description="Rubric display title")
    description: str | None = Field(
        default=None, max_length=1000, description="Optional rubric description"
    )
    criteria: list[RubricCriterion] = Field(
        min_length=1, max_length=10, description="Scoring criteria list"
    )


class JudgeEvaluationScore(BaseModel):
    """Structured response produced by the judge model for a candidate model generation."""

    criterion_scores: dict[str, float] = Field(
        description="Individual criteria scores from 0.0 to 1.0 (or 1 to 5 normalized)"
    )
    overall_score: float = Field(
        ge=0.0, le=1.0, description="Weighted composite score between 0.0 and 1.0"
    )
    reasoning: str = Field(description="Judge rationale explaining the assigned scores")


class JudgeEvaluationRequest(BaseModel):
    """Payload to invoke LLM-as-Judge scoring for a specific model generation."""

    prompt: str = Field(description="Original user prompt")
    model_output: str = Field(description="Candidate model response text")
    task_type: TaskType = Field(default=TaskType.QUESTION_ANSWERING)
    reference_output: str | None = Field(
        default=None, description="Optional ground truth reference"
    )
    custom_rubric: RubricSchema | None = Field(default=None, description="Optional override rubric")
