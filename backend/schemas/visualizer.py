"""Pydantic v2 schemas for 2D Embedding Projection & Visualizer."""

from pydantic import BaseModel, ConfigDict, Field


class EmbeddingPoint(BaseModel):
    """A 2D projected data point representing a prompt, reference, or model output."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(description="Point identifier (model_id, 'prompt', or 'reference')")
    label: str = Field(description="Display label")
    point_type: str = Field(description="'prompt', 'reference', or 'candidate'")
    x: float = Field(description="2D coordinate X")
    y: float = Field(description="2D coordinate Y")
    text_snippet: str = Field(description="Truncated text preview")


class EmbeddingVisualizationRequest(BaseModel):
    """Payload to compute 2D semantic embedding projections for a set of texts."""

    model_config = ConfigDict(str_strip_whitespace=True)

    prompt: str = Field(min_length=1, max_length=50000, description="Evaluation prompt")
    reference_output: str | None = Field(
        default=None, max_length=50000, description="Ground truth reference text"
    )
    candidate_responses: dict[str, str] = Field(
        min_length=1, description="Map of model identifier to output text"
    )


class EmbeddingVisualizationResponse(BaseModel):
    """2D coordinate clusters and semantic similarity matrix for visualization."""

    model_config = ConfigDict(from_attributes=True)

    points: list[EmbeddingPoint] = Field(description="Projected 2D coordinates")
    similarity_matrix: dict[str, dict[str, float]] = Field(
        description="Pairwise cosine similarity matrix"
    )
    method: str = Field(
        default="semantic_mds", description="Reduction method: 'umap' or 'semantic_mds'"
    )
