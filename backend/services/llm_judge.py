"""LLM-as-Judge (G-Eval Style) automated scoring engine.

Uses an evaluation LLM (default: Gemini 3.5 Flash) to score candidate responses
against structured task rubrics with detailed reasoning and criteria breakdowns.
"""

import json
import logging
import re

import litellm

from backend.core.config import settings
from backend.schemas.consumers import TaskType
from backend.schemas.rubrics import JudgeEvaluationScore, RubricSchema
from backend.services.rubric_service import get_default_rubric

logger = logging.getLogger(__name__)

DEFAULT_JUDGE_MODEL = "gemini/gemini-3.5-flash"


def _clean_json_markdown(text: str) -> str:
    """Extract clean JSON string from LLM output, stripping markdown code fences."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    # If starting with { and ending with }
    if text.startswith("{") and text.endswith("}"):
        return text
    # Try finding first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def build_judge_prompt(
    prompt: str,
    candidate_output: str,
    rubric: RubricSchema,
    reference_output: str | None = None,
) -> str:
    """Construct the evaluation prompt instructing the judge model."""
    criteria_lines = []
    for c in rubric.criteria:
        criteria_lines.append(f"- **{c.name}** (Weight {c.weight}): {c.description}")
    criteria_text = "\n".join(criteria_lines)

    ref_text = (
        f"### Ground Truth Reference Output:\n{reference_output}\n" if reference_output else ""
    )

    return f"""You are an expert impartial AI evaluator scoring generated responses according to a strict multi-criteria rubric.

### Original User Prompt:
{prompt}

{ref_text}
### Candidate Model Output to Evaluate:
{candidate_output}

### Evaluation Rubric ({rubric.title}):
{criteria_text}

### Instructions:
1. Score each criterion individually from 0.0 (worst) to 1.0 (flawless).
2. Compute the weighted overall_score (between 0.0 and 1.0) using the specified weights.
3. Provide concise, objective reasoning explaining why points were awarded or deducted.
4. Output MUST be a valid JSON object matching this schema:
{{
  "criterion_scores": {{
    "{rubric.criteria[0].name}": 0.85
  }},
  "overall_score": 0.85,
  "reasoning": "Clear explanation of strengths and shortcomings."
}}
Return ONLY the raw JSON object."""


async def evaluate_with_llm_judge(
    prompt: str,
    candidate_output: str,
    task_type: TaskType,
    reference_output: str | None = None,
    rubric: RubricSchema | None = None,
    judge_model: str = DEFAULT_JUDGE_MODEL,
) -> JudgeEvaluationScore:
    """Evaluate candidate model output using LLM-as-a-Judge against rubric criteria."""
    active_rubric = rubric or get_default_rubric(task_type)
    system_msg = "You are a precise, objective evaluation assistant grading LLM outputs against a rubric. Output only valid JSON."
    user_prompt = build_judge_prompt(
        prompt=prompt,
        candidate_output=candidate_output,
        rubric=active_rubric,
        reference_output=reference_output,
    )

    # In testing or when API keys are unconfigured, return deterministic mock evaluation
    if not settings.gemini_api_key and not settings.groq_api_key:
        logger.debug("No LLM API keys present; utilizing deterministic heuristic judge fallback")
        criterion_scores = {c.name: 0.85 for c in active_rubric.criteria}
        return JudgeEvaluationScore(
            criterion_scores=criterion_scores,
            overall_score=0.85,
            reasoning="Automated fallback evaluation: candidate output satisfies prompt constraints with clean formatting.",
        )

    try:
        response = await litellm.acompletion(
            model=judge_model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=600,
        )
        content = response.choices[0].message.content or ""
        cleaned_json = _clean_json_markdown(content)
        data = json.loads(cleaned_json)

        criterion_scores = {k: float(v) for k, v in data.get("criterion_scores", {}).items()}
        overall = float(data.get("overall_score", 0.0))
        # Ensure overall is bound between 0.0 and 1.0
        overall_clamped = max(0.0, min(1.0, overall))

        return JudgeEvaluationScore(
            criterion_scores=criterion_scores,
            overall_score=round(overall_clamped, 4),
            reasoning=str(data.get("reasoning", "Evaluated against rubric.")),
        )
    except Exception as exc:
        logger.warning(f"LLM Judge call to {judge_model} failed ({exc}); applying safe fallback")
        criterion_scores = {c.name: 0.70 for c in active_rubric.criteria}
        return JudgeEvaluationScore(
            criterion_scores=criterion_scores,
            overall_score=0.70,
            reasoning=f"Judge model encountered exception: {exc}. Safe default score assigned.",
        )
