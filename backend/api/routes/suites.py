"""API routes for Regression Testing Suites, automated execution, and delta comparison."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.schemas.suite import (
    PromptSuiteCreate,
    PromptSuiteSchema,
    RegressionReport,
    SuiteRunRecord,
    SuiteRunRequest,
)
from backend.services.suite_service import (
    generate_regression_report,
    get_prompt_suite,
    list_prompt_suites,
    list_suite_runs,
    run_prompt_suite,
    save_prompt_suite,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/suites", tags=["Regression Testing Suites"])


@router.post("", response_model=PromptSuiteSchema, status_code=status.HTTP_201_CREATED)
async def create_suite(payload: PromptSuiteCreate) -> PromptSuiteSchema:
    """Create and persist a new benchmark prompt suite."""
    try:
        return await save_prompt_suite(payload)
    except Exception as exc:
        logger.error(f"Failed to create prompt suite: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create suite: {exc}",
        ) from exc


@router.get("", response_model=list[PromptSuiteSchema])
async def get_all_suites() -> list[PromptSuiteSchema]:
    """Retrieve all persisted prompt benchmark suites."""
    return await list_prompt_suites()


@router.get("/{suite_id}", response_model=PromptSuiteSchema)
async def get_suite(suite_id: UUID) -> PromptSuiteSchema:
    """Retrieve a specific benchmark suite by ID."""
    suite = await get_prompt_suite(suite_id)
    if not suite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt suite {suite_id} not found",
        )
    return suite


@router.post("/{suite_id}/run", response_model=SuiteRunRecord)
async def run_suite(suite_id: UUID, payload: SuiteRunRequest) -> SuiteRunRecord:
    """Execute all prompts in a suite across target models."""
    try:
        return await run_prompt_suite(
            suite_id=suite_id,
            models=payload.models,
            consumer_id=payload.consumer_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(f"Error running suite {suite_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run suite: {exc}",
        ) from exc


@router.get("/{suite_id}/runs", response_model=list[SuiteRunRecord])
async def get_suite_runs(suite_id: UUID) -> list[SuiteRunRecord]:
    """Retrieve all executed benchmark runs for a specific suite."""
    return await list_suite_runs(suite_id)


@router.get("/{suite_id}/regression-report", response_model=RegressionReport)
async def get_regression_report(
    suite_id: UUID,
    baseline_run_id: Annotated[UUID, Query(description="Baseline suite run ID")],
    candidate_run_id: Annotated[
        UUID, Query(description="Candidate suite run ID to compare against baseline")
    ],
) -> RegressionReport:
    """Compare two suite execution runs and generate a regression report with per-prompt deltas."""
    try:
        return await generate_regression_report(
            suite_id=suite_id,
            baseline_run_id=baseline_run_id,
            candidate_run_id=candidate_run_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(f"Failed to compute regression report: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate regression report: {exc}",
        ) from exc
