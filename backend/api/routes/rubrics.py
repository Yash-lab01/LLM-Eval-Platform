"""API routes for Custom Evaluation Rubrics and LLM-as-Judge scoring."""

import logging

from fastapi import APIRouter, HTTPException, status

from backend.schemas.consumers import TaskType
from backend.schemas.rubrics import (
    JudgeEvaluationRequest,
    JudgeEvaluationScore,
    RubricSchema,
)
from backend.services.llm_judge import evaluate_with_llm_judge
from backend.services.rubric_service import (
    get_rubric_for_task,
    list_all_rubrics,
    save_custom_rubric,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rubrics", tags=["Evaluation Rubrics"])


@router.get("", response_model=list[RubricSchema])
async def get_all_rubrics() -> list[RubricSchema]:
    """Retrieve all evaluation rubrics across all task categories."""
    return await list_all_rubrics()


@router.get("/{task_type}", response_model=RubricSchema)
async def get_rubric(task_type: TaskType) -> RubricSchema:
    """Retrieve the active evaluation rubric for a specific task category."""
    try:
        return await get_rubric_for_task(task_type)
    except Exception as exc:
        logger.error(f"Error fetching rubric for {task_type}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve rubric",
        ) from exc


@router.post("", response_model=RubricSchema, status_code=status.HTTP_201_CREATED)
async def create_or_update_rubric(rubric: RubricSchema) -> RubricSchema:
    """Register or update a custom evaluation rubric for a task category."""
    try:
        saved = await save_custom_rubric(rubric)
        logger.info(f"Custom rubric persisted for task {rubric.task_type.value}")
        return saved
    except Exception as exc:
        logger.error(f"Failed to save rubric: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save custom rubric",
        ) from exc


@router.post("/judge", response_model=JudgeEvaluationScore)
async def judge_response(request: JudgeEvaluationRequest) -> JudgeEvaluationScore:
    """Evaluate a candidate model response using LLM-as-a-Judge against rubric criteria."""
    try:
        score = await evaluate_with_llm_judge(
            prompt=request.prompt,
            candidate_output=request.model_output,
            task_type=request.task_type,
            reference_output=request.reference_output,
            rubric=request.custom_rubric,
        )
        return score
    except Exception as exc:
        logger.error(f"LLM Judge evaluation failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM Judge evaluation failed: {exc}",
        ) from exc
