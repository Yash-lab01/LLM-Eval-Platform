"""Embedding Visualizer Service.

Generates 2D dimensionality-reduced scatter plot projections comparing
prompt, reference truth, and candidate model outputs.
Supports UMAP when available with deterministic semantic Multidimensional Scaling (MDS) fallback.
"""

import math
import re
from typing import TYPE_CHECKING

from backend.schemas.visualizer import (
    EmbeddingPoint,
    EmbeddingVisualizationResponse,
)

if TYPE_CHECKING:
    pass


def _tokenize_text(text: str) -> set[str]:
    """Extract normalized alphanumeric word tokens."""
    return set(re.findall(r"\b\w+\b", text.lower()))


def _compute_pairwise_similarity(text_a: str, text_b: str) -> float:
    """Compute cosine similarity of token frequency sets between two texts."""
    tokens_a = _tokenize_text(text_a)
    tokens_b = _tokenize_text(text_b)

    if not tokens_a or not tokens_b:
        return 0.0

    common = tokens_a.intersection(tokens_b)
    if not common:
        return 0.0

    # Normalized overlap coefficient (approximate cosine similarity)
    denom = math.sqrt(len(tokens_a) * len(tokens_b))
    return round(float(len(common) / denom), 4)


def generate_2d_embeddings(
    prompt: str,
    candidate_responses: dict[str, str],
    reference_output: str | None = None,
) -> EmbeddingVisualizationResponse:
    """Calculate 2D scatter coordinates and pairwise similarity matrix."""
    items: list[tuple[str, str, str, str]] = []  # (id, label, point_type, text)

    # 1. Register prompt
    items.append(("prompt", "Original Prompt", "prompt", prompt))

    # 2. Register reference if present
    if reference_output and reference_output.strip():
        items.append(("reference", "Ground Truth Reference", "reference", reference_output))

    # 3. Register candidate model outputs
    for model_id, output in candidate_responses.items():
        label = model_id.split("/")[-1] if "/" in model_id else model_id
        items.append((model_id, label, "candidate", output))

    # 4. Compute Pairwise Similarity Matrix
    sim_matrix: dict[str, dict[str, float]] = {}
    for id_a, _, _, text_a in items:
        sim_matrix[id_a] = {}
        for id_b, _, _, text_b in items:
            if id_a == id_b:
                sim_matrix[id_a][id_b] = 1.0
            else:
                sim_matrix[id_a][id_b] = _compute_pairwise_similarity(text_a, text_b)

    points: list[EmbeddingPoint] = []
    reduction_method = "semantic_mds"

    try:
        # Check if umap and numpy are installed
        import numpy as np  # type: ignore # noqa: F401
        import umap  # type: ignore

        # Construct basic TF-IDF style feature matrix
        vocab = sorted({w for _, _, _, text in items for w in _tokenize_text(text)})
        word_to_idx = {w: i for i, w in enumerate(vocab)}

        matrix = []
        for _, _, _, text in items:
            vec = [0.0] * len(vocab)
            for w in _tokenize_text(text):
                if w in word_to_idx:
                    vec[word_to_idx[w]] += 1.0
            matrix.append(vec)

        reducer = umap.UMAP(n_components=2, n_neighbors=min(5, len(items)), random_state=42)
        coords = reducer.fit_transform(matrix)

        for idx, (item_id, label, point_type, text) in enumerate(items):
            snippet = text[:120] + ("..." if len(text) > 120 else "")
            points.append(
                EmbeddingPoint(
                    id=item_id,
                    label=label,
                    point_type=point_type,
                    x=round(float(coords[idx][0]), 4),
                    y=round(float(coords[idx][1]), 4),
                    text_snippet=snippet,
                )
            )
        reduction_method = "umap"
    except Exception:
        # Deterministic semantic distance placement fallback
        has_reference = any(p[0] == "reference" for p in items)
        ref_text = reference_output if has_reference and reference_output else prompt

        candidate_items = [p for p in items if p[2] == "candidate"]
        total_candidates = len(candidate_items)

        # Place prompt and reference anchors
        if has_reference:
            points.append(
                EmbeddingPoint(
                    id="reference",
                    label="Ground Truth Reference",
                    point_type="reference",
                    x=0.0,
                    y=0.0,
                    text_snippet=(reference_output or "")[:120],
                )
            )
            points.append(
                EmbeddingPoint(
                    id="prompt",
                    label="Original Prompt",
                    point_type="prompt",
                    x=-1.5,
                    y=0.0,
                    text_snippet=prompt[:120],
                )
            )
        else:
            points.append(
                EmbeddingPoint(
                    id="prompt",
                    label="Original Prompt",
                    point_type="prompt",
                    x=0.0,
                    y=0.0,
                    text_snippet=prompt[:120],
                )
            )

        # Project candidate models on radial arc based on similarity
        for idx, (item_id, label, point_type, text) in enumerate(candidate_items):
            sim_to_target = _compute_pairwise_similarity(text, ref_text)
            # Distance: higher similarity = closer to origin
            radius = 0.3 + (1.0 - sim_to_target) * 1.5

            # Angle distributed across upper and lower hemisphere
            if total_candidates > 1:
                angle = -math.pi / 2.0 + (math.pi * (idx + 0.5) / total_candidates)
            else:
                angle = 0.0

            x = round(radius * math.cos(angle) + (0.5 if not has_reference else 0.0), 4)
            y = round(radius * math.sin(angle), 4)
            snippet = text[:120] + ("..." if len(text) > 120 else "")

            points.append(
                EmbeddingPoint(
                    id=item_id,
                    label=label,
                    point_type=point_type,
                    x=x,
                    y=y,
                    text_snippet=snippet,
                )
            )

    return EmbeddingVisualizationResponse(
        points=points,
        similarity_matrix=sim_matrix,
        method=reduction_method,
    )
