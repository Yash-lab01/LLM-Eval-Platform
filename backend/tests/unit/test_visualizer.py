"""Unit tests for 2D Embedding Visualizer and projection coordinates."""

from backend.services.visualizer import (
    _compute_pairwise_similarity,
    _tokenize_text,
    generate_2d_embeddings,
)


def test_tokenize_and_similarity():
    """Verify text tokenization and pairwise similarity computation."""
    tokens = _tokenize_text("The quick brown fox jumps over the lazy dog!")
    assert "quick" in tokens
    assert "fox" in tokens
    assert "the" in tokens

    sim_identical = _compute_pairwise_similarity("hello world", "hello world")
    assert sim_identical == 1.0

    sim_similar = _compute_pairwise_similarity(
        "Paris is the capital of France",
        "France's capital city is Paris",
    )
    assert sim_similar >= 0.50

    sim_unrelated = _compute_pairwise_similarity(
        "Quantum mechanics deals with atomic particles",
        "Cooking pasta requires boiling salted water",
    )
    assert sim_unrelated == 0.0


def test_generate_2d_embeddings_with_reference():
    """Verify 2D projection places similar models closer to reference than divergent models."""
    prompt = "Explain photosynthesis"
    reference = (
        "Photosynthesis converts carbon dioxide and water into glucose and oxygen using sunlight."
    )
    candidate_responses = {
        "gemini/gemini-3.5-flash": "Plants use sunlight to turn carbon dioxide and water into glucose sugar and oxygen.",
        "groq/openai/gpt-oss-120b": "Photosynthesis is the cellular biological conversion of light energy into sugar.",
        "ollama/mistral": "The solar system consists of eight planets orbiting the central Sun in elliptical orbits.",
    }

    resp = generate_2d_embeddings(
        prompt=prompt,
        candidate_responses=candidate_responses,
        reference_output=reference,
    )

    assert len(resp.points) == 5  # prompt + reference + 3 candidates
    point_ids = {p.id for p in resp.points}
    assert "prompt" in point_ids
    assert "reference" in point_ids
    assert "gemini/gemini-3.5-flash" in point_ids

    # Similarity matrix checks
    assert "reference" in resp.similarity_matrix
    assert resp.similarity_matrix["reference"]["gemini/gemini-3.5-flash"] > 0.40
    assert resp.similarity_matrix["reference"]["ollama/mistral"] < 0.15

    # Distance to reference: Gemini should be closer to (0,0) than Mistral (off-topic)
    ref_pt = next(p for p in resp.points if p.id == "reference")
    gemini_pt = next(p for p in resp.points if p.id == "gemini/gemini-3.5-flash")
    mistral_pt = next(p for p in resp.points if p.id == "ollama/mistral")

    gemini_dist = (gemini_pt.x - ref_pt.x) ** 2 + (gemini_pt.y - ref_pt.y) ** 2
    mistral_dist = (mistral_pt.x - ref_pt.x) ** 2 + (mistral_pt.y - ref_pt.y) ** 2

    assert gemini_dist < mistral_dist


def test_generate_2d_embeddings_without_reference():
    """Verify 2D projection works gracefully when no ground truth reference is provided."""
    prompt = "Write a haiku about autumn"
    candidates = {
        "gemini/gemini-3.5-flash": "Golden leaves fall down / Crisp wind blows across the trees / Winter is arriving",
        "groq/qwen/qwen3-32b": "Autumn leaves descend / Cold whisper in the forest / Nature goes to sleep",
    }

    resp = generate_2d_embeddings(
        prompt=prompt,
        candidate_responses=candidates,
        reference_output=None,
    )

    assert len(resp.points) == 3  # prompt + 2 candidates
    assert any(p.point_type == "prompt" for p in resp.points)
    assert sum(1 for p in resp.points if p.point_type == "candidate") == 2
