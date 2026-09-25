"""FastMCP Server for LLM Evaluation & Benchmarking Platform.

Exposes evaluation engine, empirical model leaderboard recommendations,
historical summaries, and run comparisons as standardized MCP tools.

Supports dual transport:
- stdio: for Cursor, Claude Desktop, and CLI usage
- sse/streamable-http: for dockerized and network deployment on port 8001
"""

import logging
import os
import sys
import uuid

from fastmcp import FastMCP
from sqlalchemy import select

from backend.core.database import AsyncSessionFactory
from backend.models.eval import EvalRun
from backend.schemas.consumers import EvalConsumerConfig, FeatureFlag, ScoringMetric, TaskType
from backend.schemas.eval import (
    EvalRunResult,
    EvalRunSummary,
    PromptRunRequest,
    RunComparison,
)
from backend.schemas.leaderboard import ModelRecommendation
from backend.schemas.models import ModelID
from backend.services.eval_runner import run_parallel_eval
from backend.services.leaderboard import get_model_recommendation
from backend.services.run_comparison import compare_eval_runs

# Ensure all logs go to stderr to prevent corrupting stdio transport
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mcp-server")

# Initialize FastMCP Server
mcp = FastMCP("llm-eval-platform")


@mcp.tool()
async def health_check() -> dict:
    """Check MCP server health and connectivity status."""
    return {"status": "healthy", "service": "llm-eval-mcp-server"}


@mcp.tool()
async def run_eval(
    prompt: str,
    task_type: str = "question_answering",
    models: list[str] | None = None,
    consumer_id: str | None = None,
    features: list[str] | None = None,
    reference_output: str | None = None,
) -> EvalRunResult:
    """Run an evaluation benchmark for a prompt across multiple target LLMs.

    Executes models in parallel, scores outputs (BERTScore, ROUGE-L, latency, cost),
    persists telemetry in PostgreSQL, and returns full scored results with winner.
    """
    logger.info(f"MCP tool run_eval called with prompt length {len(prompt)}")

    # 1. Resolve task type
    try:
        resolved_task = TaskType(task_type)
    except ValueError:
        resolved_task = TaskType.QUESTION_ANSWERING

    # 2. Resolve models
    resolved_models: list[ModelID] = []
    if models:
        for m in models:
            try:
                resolved_models.append(ModelID(m))
            except ValueError:
                logger.warning(f"Unrecognized model {m} in MCP run_eval call; skipping")
    if not resolved_models:
        resolved_models = [ModelID.GEMINI_3_5_FLASH, ModelID.GROQ_GPT_OSS_20B]

    # 3. Resolve features & consumer config
    consumer_config: EvalConsumerConfig | None = None
    if features:
        feature_flags = [FeatureFlag(f) for f in features if f in FeatureFlag._value2member_map_]
        if feature_flags:
            consumer_config = EvalConsumerConfig(
                consumer_id=consumer_id or "mcp-agent",
                features=feature_flags,
                models=resolved_models,
                task_type=resolved_task,
            )

    scoring_metrics = [
        ScoringMetric.LATENCY,
        ScoringMetric.TOKEN_COUNT,
        ScoringMetric.ESTIMATED_COST,
    ]
    if reference_output and reference_output.strip():
        scoring_metrics.extend([ScoringMetric.BERT_SCORE, ScoringMetric.ROUGE_L])

    request = PromptRunRequest(
        prompt=prompt,
        task_type=resolved_task,
        models=resolved_models,
        consumer_id=consumer_id,
        consumer_config=consumer_config,
        scoring_metrics=scoring_metrics,
        reference_output=reference_output,
    )

    run_id = uuid.uuid4()

    async with AsyncSessionFactory() as session:
        # Create initial pending run
        eval_run_orm = EvalRun(
            id=run_id,
            prompt_text=request.prompt,
            task_type=request.task_type.value,
            models=[m.value for m in request.models],
            reference_output=request.reference_output,
            status="pending",
        )
        session.add(eval_run_orm)
        await session.commit()

        # Run parallel execution and scoring
        return await run_parallel_eval(run_id=run_id, request=request, session=session)


@mcp.tool()
async def get_best_model(
    task_type: str = "question_answering",
    metric: str = "bert_score",
) -> ModelRecommendation:
    """Recommend the optimal LLM for a given task type based on empirical leaderboard benchmarks."""
    logger.info(f"MCP tool get_best_model called: task={task_type}, metric={metric}")

    try:
        resolved_task = TaskType(task_type)
    except ValueError:
        resolved_task = TaskType.QUESTION_ANSWERING

    try:
        resolved_metric = ScoringMetric(metric)
    except ValueError:
        resolved_metric = ScoringMetric.BERT_SCORE

    async with AsyncSessionFactory() as session:
        return await get_model_recommendation(
            task_type=resolved_task,
            metric=resolved_metric,
            session=session,
        )


@mcp.tool()
async def get_eval_history(
    consumer_id: str | None = None,
    limit: int = 20,
) -> list[EvalRunSummary]:
    """Retrieve recent evaluation run summaries, optionally filtered by consumer ID."""
    logger.info(f"MCP tool get_eval_history called: consumer={consumer_id}, limit={limit}")

    async with AsyncSessionFactory() as session:
        query = select(EvalRun).order_by(EvalRun.created_at.desc())
        if consumer_id:
            try:
                c_uuid = uuid.UUID(consumer_id)
                query = query.where(EvalRun.consumer_id == c_uuid)
            except ValueError:
                pass

        query = query.limit(min(max(1, limit), 100))
        result = await session.execute(query)
        runs = result.scalars().all()

        return [
            EvalRunSummary(
                run_id=r.id,
                consumer_id=r.consumer_id,
                task_type=TaskType(r.task_type),
                models=[ModelID(m) for m in r.models],
                status=r.status,
                created_at=r.created_at,
                completed_at=r.completed_at,
            )
            for r in runs
        ]


@mcp.tool()
async def compare_runs(
    run_id_a: str,
    run_id_b: str,
) -> RunComparison:
    """Compare performance metrics and compute score deltas between two evaluation runs."""
    logger.info(f"MCP tool compare_runs called: a={run_id_a}, b={run_id_b}")

    async with AsyncSessionFactory() as session:
        return await compare_eval_runs(
            run_id_a=uuid.UUID(run_id_a),
            run_id_b=uuid.UUID(run_id_b),
            session=session,
        )


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if transport in ("http", "sse"):
        port = int(os.getenv("MCP_PORT", "8001"))
        host = os.getenv("MCP_HOST", "0.0.0.0")
        logger.info(f"Starting FastMCP SSE server on {host}:{port}")
        mcp.run(transport="sse", host=host, port=port)
    else:
        # stdio mode: all logs must go to stderr
        logger.info("Starting FastMCP server in stdio mode")
        mcp.run(transport="stdio")
