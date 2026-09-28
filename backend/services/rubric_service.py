"""Rubric Service for managing task-specific evaluation rubrics.

Provides built-in standardized G-eval rubrics for all supported task types
and allows registration of custom criteria.
"""

import logging

from backend.core.redis_client import get_redis_client
from backend.schemas.consumers import TaskType
from backend.schemas.rubrics import RubricCriterion, RubricSchema

logger = logging.getLogger(__name__)

# Standard built-in evaluation rubrics
DEFAULT_RUBRICS: dict[TaskType, RubricSchema] = {
    TaskType.CODE_GENERATION: RubricSchema(
        task_type=TaskType.CODE_GENERATION,
        title="Code Correctness & Quality Rubric",
        description="Evaluates functional correctness, structure, and edge case handling of generated code.",
        criteria=[
            RubricCriterion(
                name="correctness",
                weight=0.45,
                description="Does the code correctly solve the stated problem and follow requested signatures?",
            ),
            RubricCriterion(
                name="quality_readability",
                weight=0.30,
                description="Is the code clean, well-formatted, idiomatic, and documented appropriately?",
            ),
            RubricCriterion(
                name="error_handling_resilience",
                weight=0.25,
                description="Does the solution consider error states, edge cases, and resource cleanup?",
            ),
        ],
    ),
    TaskType.SUMMARIZATION: RubricSchema(
        task_type=TaskType.SUMMARIZATION,
        title="Summarization Quality Rubric",
        description="Assesses coverage of critical points, conciseness, and faithfulness to source text.",
        criteria=[
            RubricCriterion(
                name="coverage",
                weight=0.40,
                description="Are all core concepts and key points accurately represented?",
            ),
            RubricCriterion(
                name="conciseness",
                weight=0.30,
                description="Is the summary free of unnecessary repetition, filler words, or verbosity?",
            ),
            RubricCriterion(
                name="factuality",
                weight=0.30,
                description="Does the summary remain strictly faithful to facts in the original context?",
            ),
        ],
    ),
    TaskType.QUESTION_ANSWERING: RubricSchema(
        task_type=TaskType.QUESTION_ANSWERING,
        title="Direct Question Answering Rubric",
        description="Grades answer accuracy, explanatory clarity, and complete resolution of user query.",
        criteria=[
            RubricCriterion(
                name="accuracy",
                weight=0.50,
                description="Is the answer factually and logically accurate in addressing the specific question?",
            ),
            RubricCriterion(
                name="clarity",
                weight=0.30,
                description="Is the explanation understandable, well-reasoned, and unambiguous?",
            ),
            RubricCriterion(
                name="completeness",
                weight=0.20,
                description="Does the response address all sub-questions or constraints in the prompt?",
            ),
        ],
    ),
    TaskType.DATA_EXTRACTION: RubricSchema(
        task_type=TaskType.DATA_EXTRACTION,
        title="Data Extraction & Format Rubric",
        description="Evaluates JSON/schema adherence and precision of extracted entities and values.",
        criteria=[
            RubricCriterion(
                name="format_adherence",
                weight=0.50,
                description="Does the output strictly comply with the requested format (e.g. valid JSON, schema keys)?",
            ),
            RubricCriterion(
                name="precision_recall",
                weight=0.50,
                description="Are extracted fields exact and complete without hallucinations or omitted entities?",
            ),
        ],
    ),
    TaskType.CREATIVE_WRITING: RubricSchema(
        task_type=TaskType.CREATIVE_WRITING,
        title="Creative Writing & Style Rubric",
        description="Assesses tone, originality, narrative flow, and engagement.",
        criteria=[
            RubricCriterion(
                name="creativity_voice",
                weight=0.40,
                description="Does the writing demonstrate engaging voice, style, and imaginative execution?",
            ),
            RubricCriterion(
                name="narrative_flow",
                weight=0.35,
                description="Is the structure coherent, well-paced, and logically cohesive?",
            ),
            RubricCriterion(
                name="prompt_compliance",
                weight=0.25,
                description="Did the generation satisfy all thematic and stylistic constraints specified?",
            ),
        ],
    ),
    TaskType.CLASSIFICATION: RubricSchema(
        task_type=TaskType.CLASSIFICATION,
        title="Classification Accuracy Rubric",
        description="Grades accuracy of assigned categorical labels and supporting rationale.",
        criteria=[
            RubricCriterion(
                name="label_correctness",
                weight=0.60,
                description="Is the predicted class or label objectively correct according to criteria?",
            ),
            RubricCriterion(
                name="justification",
                weight=0.40,
                description="Is the supporting reasoning sound, coherent, and evidence-based?",
            ),
        ],
    ),
    TaskType.TRANSLATION: RubricSchema(
        task_type=TaskType.TRANSLATION,
        title="Translation Fidelity Rubric",
        description="Assesses semantic equivalence, fluency, and idiomatic precision in target language.",
        criteria=[
            RubricCriterion(
                name="semantic_fidelity",
                weight=0.50,
                description="Does the translation accurately preserve all meaning and nuance of the source?",
            ),
            RubricCriterion(
                name="fluency",
                weight=0.50,
                description="Is the target language natural, grammatically flawless, and idiomatically sound?",
            ),
        ],
    ),
    TaskType.RAG_RESPONSE: RubricSchema(
        task_type=TaskType.RAG_RESPONSE,
        title="RAG Synthesis & Groundedness Rubric",
        description="Measures grounding in provided context documents and avoidance of external hallucination.",
        criteria=[
            RubricCriterion(
                name="faithfulness",
                weight=0.45,
                description="Are all assertions directly supported by the retrieved context chunks?",
            ),
            RubricCriterion(
                name="context_relevance",
                weight=0.30,
                description="Does the response extract the most pertinent information from the retrieved context?",
            ),
            RubricCriterion(
                name="answer_directness",
                weight=0.25,
                description="Does the answer directly resolve the user question without extraneous fluff?",
            ),
        ],
    ),
    TaskType.COMMAND_GENERATION: RubricSchema(
        task_type=TaskType.COMMAND_GENERATION,
        title="CLI & Command Syntax Rubric",
        description="Evaluates syntactical correctness, flag precision, and safety of generated shell commands.",
        criteria=[
            RubricCriterion(
                name="syntax_correctness",
                weight=0.50,
                description="Is the CLI command syntactically valid and executable without syntax errors?",
            ),
            RubricCriterion(
                name="flag_precision",
                weight=0.30,
                description="Are arguments, flags, and options configured precisely as requested?",
            ),
            RubricCriterion(
                name="safety_best_practices",
                weight=0.20,
                description="Does the command avoid destructive side-effects and observe safe practices?",
            ),
        ],
    ),
}


_CUSTOM_RUBRICS_IN_MEMORY: dict[str, RubricSchema] = {}


def get_default_rubric(task_type: TaskType) -> RubricSchema:
    """Retrieve the standard built-in rubric for a specific task category."""
    if task_type in DEFAULT_RUBRICS:
        return DEFAULT_RUBRICS[task_type]
    # Fallback to general question answering rubric
    return DEFAULT_RUBRICS[TaskType.QUESTION_ANSWERING]


async def get_rubric_for_task(task_type: TaskType) -> RubricSchema:
    """Retrieve rubric for task type, checking Redis cache or memory for custom overrides first."""
    try:
        redis_client = get_redis_client()
        cached = await redis_client.get(f"rubric:{task_type.value}")
        if cached:
            return RubricSchema.model_validate_json(cached)
    except Exception as exc:
        logger.debug(f"Redis rubric cache lookup failed: {exc}")

    if task_type.value in _CUSTOM_RUBRICS_IN_MEMORY:
        return _CUSTOM_RUBRICS_IN_MEMORY[task_type.value]

    return get_default_rubric(task_type)


async def save_custom_rubric(rubric: RubricSchema) -> RubricSchema:
    """Persist a custom rubric into Redis cache and in-memory store."""
    _CUSTOM_RUBRICS_IN_MEMORY[rubric.task_type.value] = rubric
    try:
        redis_client = get_redis_client()
        await redis_client.set(
            f"rubric:{rubric.task_type.value}",
            rubric.model_dump_json(),
        )
    except Exception as exc:
        logger.warning(f"Failed to persist custom rubric to Redis: {exc}")

    return rubric


async def list_all_rubrics() -> list[RubricSchema]:
    """List all rubrics across all task categories, incorporating custom overrides."""
    rubrics_map = dict(DEFAULT_RUBRICS)
    # Overlay in-memory custom rubrics
    for key, custom in _CUSTOM_RUBRICS_IN_MEMORY.items():
        try:
            rubrics_map[TaskType(key)] = custom
        except ValueError:
            pass
    return list(rubrics_map.values())
