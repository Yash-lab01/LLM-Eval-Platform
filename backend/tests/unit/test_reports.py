"""Unit tests for Executive Evaluation Report generation in HTML and PDF formats."""

from datetime import UTC, datetime
from uuid import uuid4

from backend.schemas.consumers import TaskType
from backend.schemas.eval import (
    EvalRunResult,
    EvalScoreSchema,
    ModelResponseSchema,
)
from backend.schemas.models import ModelID
from backend.services.report_service import generate_pdf_report, render_html_report


def test_render_html_report():
    """Verify Jinja2 template renders valid HTML with scores, inputs, and winner banner."""
    run_id = uuid4()
    run = EvalRunResult(
        run_id=run_id,
        prompt="Explain Docker containers to a beginner.",
        task_type=TaskType.QUESTION_ANSWERING,
        models=[ModelID.GEMINI_3_5_FLASH, ModelID.GROQ_GPT_OSS_120B],
        status="completed",
        reference_output="Docker packages software into isolated containers.",
        winner=ModelID.GEMINI_3_5_FLASH,
        created_at=datetime.now(UTC),
        responses=[
            ModelResponseSchema(
                model_id=ModelID.GEMINI_3_5_FLASH,
                output="Docker lets you package applications with their dependencies.",
                latency_ms=160.0,
                token_count=35,
            ),
            ModelResponseSchema(
                model_id=ModelID.GROQ_GPT_OSS_120B,
                output="Containers provide lightweight virtualization for apps.",
                latency_ms=220.0,
                token_count=30,
            ),
        ],
        scores=[
            EvalScoreSchema(
                model_id=ModelID.GEMINI_3_5_FLASH,
                bert_score_f1=0.88,
                rouge_l=0.82,
                llm_judge_score=0.90,
                hallucination_score=0.05,
                latency_ms=160.0,
                token_count=35,
                estimated_cost_usd=0.0001,
            ),
            EvalScoreSchema(
                model_id=ModelID.GROQ_GPT_OSS_120B,
                bert_score_f1=0.80,
                rouge_l=0.75,
                llm_judge_score=0.82,
                hallucination_score=0.15,
                latency_ms=220.0,
                token_count=30,
                estimated_cost_usd=0.00015,
            ),
        ],
    )

    html = render_html_report(run)
    assert "<!DOCTYPE html>" in html
    assert str(run_id) in html
    assert "Explain Docker containers to a beginner." in html
    assert "gemini/gemini-3.5-flash" in html
    assert "WINNER" in html
    assert "0.8800" in html


def test_generate_pdf_report_graceful_handling():
    """Verify generate_pdf_report executes cleanly without uncaught exceptions."""
    run = EvalRunResult(
        run_id=uuid4(),
        prompt="Sample",
        task_type=TaskType.QUESTION_ANSWERING,
        models=[ModelID.GEMINI_3_5_FLASH],
        status="completed",
        created_at=datetime.now(UTC),
    )
    result = generate_pdf_report(run)
    # Result should either be PDF binary bytes or None (if weasyprint missing)
    assert result is None or isinstance(result, bytes)
