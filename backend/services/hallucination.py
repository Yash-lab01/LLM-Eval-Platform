"""Hallucination Detection Service.

Calculates sentence-level factual consistency and ungrounded claim risk
between generated model responses and source reference/context documents.
Non-blocking execution of heavy PyTorch NLI models via loop.run_in_executor,
with deterministic semantic claim-overlap fallback for lightweight/offline environments.
"""

import asyncio
import logging
import re
from typing import TYPE_CHECKING

from backend.schemas.hallucination import (
    HallucinationAnalysisResult,
    SentenceHallucinationDetail,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Basic English stopwords for content token extraction in fallback heuristic
STOPWORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "aren't",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "don't",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "isn't",
    "it",
    "it's",
    "its",
    "itself",
    "just",
    "me",
    "more",
    "most",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "now",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "wasn't",
    "we",
    "were",
    "weren't",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "with",
    "won't",
    "would",
    "you",
    "your",
    "yours",
    "yourself",
    "yourselves",
}

NEGATIONS = {
    "not",
    "no",
    "never",
    "cannot",
    "neither",
    "nor",
    "none",
    "false",
    "untrue",
    "incorrect",
    "without",
}


def split_into_sentences(text: str) -> list[str]:
    """Segment paragraph text into individual grammatical sentences."""
    if not text or not text.strip():
        return []
    # Split on terminal punctuation followed by whitespace and capital letter or end of string
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    cleaned = [s.strip() for s in sentences if s.strip()]
    return cleaned if cleaned else [text.strip()]


def _compute_sentence_hallucination_sync(sentence: str, reference: str) -> tuple[float, str]:
    """Score an individual sentence statement against the reference text.

    Returns:
        (risk_score, label) where risk is 0.0 (grounded) to 1.0 (contradictory)
        and label is 'grounded', 'unverified', or 'contradiction'.
    """
    try:
        # Attempt PyTorch cross-encoder NLI model if installed
        import torch  # type: ignore # noqa: F401
        from transformers import pipeline  # type: ignore

        nli_pipe = pipeline("text-classification", model="cross-encoder/nli-deberta-v3-base")
        res = nli_pipe({"text": reference, "text_pair": sentence})
        label = res.get("label", "").lower()
        score = float(res.get("score", 0.5))

        if "contradiction" in label:
            return round(score, 4), "contradiction"
        elif "neutral" in label:
            return round(score * 0.5, 4), "unverified"
        else:
            return round(1.0 - score, 4), "grounded"
    except Exception:
        # Semantic claim-overlap heuristic fallback
        pass

    cand_tokens = [w.lower() for w in re.findall(r"\b\w+\b", sentence)]
    ref_tokens = {w.lower() for w in re.findall(r"\b\w+\b", reference)}

    content_cand = [w for w in cand_tokens if w not in STOPWORDS and len(w) > 2]
    if not content_cand:
        return 0.0, "grounded"

    unmatched = [w for w in content_cand if w not in ref_tokens]
    unmatched_ratio = len(unmatched) / len(content_cand)

    # Check negation mismatch
    cand_has_negation = any(w in NEGATIONS for w in cand_tokens)
    ref_has_negation = any(w in NEGATIONS for w in ref_tokens)

    negation_penalty = 0.25 if cand_has_negation != ref_has_negation else 0.0
    risk = min(1.0, max(0.0, unmatched_ratio * 0.75 + negation_penalty))

    if risk >= 0.55:
        category = "contradiction"
    elif risk >= 0.30:
        category = "unverified"
    else:
        category = "grounded"

    return round(float(risk), 4), category


def _compute_hallucination_score_sync(candidate_output: str, reference_text: str) -> float:
    """Compute aggregate hallucination risk score across all sentences."""
    if not candidate_output.strip() or not reference_text.strip():
        return 0.0

    sentences = split_into_sentences(candidate_output)
    if not sentences:
        return 0.0

    scores = []
    for s in sentences:
        risk, _ = _compute_sentence_hallucination_sync(s, reference_text)
        scores.append(risk)

    avg_risk = sum(scores) / len(scores)
    max_risk = max(scores)
    # Composite: primarily average risk modulated by peak contradiction
    composite = avg_risk * 0.7 + max_risk * 0.3
    return round(float(min(1.0, max(0.0, composite))), 4)


async def compute_hallucination_score(candidate_output: str, reference_text: str) -> float:
    """Compute hallucination risk score without blocking asyncio event loop."""
    if not candidate_output.strip() or not reference_text.strip():
        return 0.0

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, _compute_hallucination_score_sync, candidate_output, reference_text
    )


async def analyze_hallucination_details(
    candidate_output: str, reference_text: str
) -> HallucinationAnalysisResult:
    """Perform comprehensive sentence-by-sentence hallucination inspection."""
    sentences = split_into_sentences(candidate_output)
    if not sentences:
        return HallucinationAnalysisResult(
            overall_hallucination_score=0.0,
            is_hallucinating=False,
            total_sentences=0,
            flagged_sentences=0,
            sentences=[],
        )

    loop = asyncio.get_running_loop()
    details: list[SentenceHallucinationDetail] = []
    risk_scores: list[float] = []

    for s in sentences:
        risk, label = await loop.run_in_executor(
            None, _compute_sentence_hallucination_sync, s, reference_text
        )
        risk_scores.append(risk)
        details.append(
            SentenceHallucinationDetail(
                sentence=s,
                risk_score=risk,
                label=label,
            )
        )

    avg_risk = sum(risk_scores) / len(risk_scores)
    max_risk = max(risk_scores)
    overall = round(min(1.0, max(0.0, avg_risk * 0.7 + max_risk * 0.3)), 4)
    flagged = sum(1 for d in details if d.label in ("unverified", "contradiction"))

    return HallucinationAnalysisResult(
        overall_hallucination_score=overall,
        is_hallucinating=overall >= 0.40,
        total_sentences=len(details),
        flagged_sentences=flagged,
        sentences=details,
    )
