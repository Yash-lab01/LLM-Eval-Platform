"""Unit tests for Batch Evaluation service: parsing, job management, processing, and CSV export."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from backend.schemas.batch import BatchPromptItem, BatchUploadRequest
from backend.schemas.consumers import TaskType
from backend.schemas.eval import EvalRunResult, EvalScoreSchema, ModelResponseSchema
from backend.schemas.models import ModelID
from backend.services.batch_service import (
    create_batch_job,
    export_batch_as_csv,
    get_batch_results,
    get_batch_status,
    parse_batch_csv,
    parse_batch_json,
    process_batch_job,
)


def test_parse_batch_csv_valid():
    """Verify parsing valid CSV text with prompt and reference columns."""
    csv_text = """id,prompt,reference_output
p1,"What is FastAPI?","FastAPI is a modern Python web framework"
p2,"Explain async/await","Async/await allows non-blocking concurrency"
"""
    items = parse_batch_csv(csv_text)
    assert len(items) == 2
    assert items[0].id == "p1"
    assert items[0].prompt == "What is FastAPI?"
    assert items[0].reference_output == "FastAPI is a modern Python web framework"
    assert items[1].id == "p2"


def test_parse_batch_csv_alternative_headers():
    """Verify parsing CSV with alternate headers like 'input' and 'ground_truth'."""
    csv_text = """input,ground_truth
"Write hello world in python","print('hello world')"
"""
    items = parse_batch_csv(csv_text)
    assert len(items) == 1
    assert items[0].prompt == "Write hello world in python"
    assert items[0].reference_output == "print('hello world')"


def test_parse_batch_json_valid():
    """Verify parsing valid JSON text with array of prompt objects."""
    json_text = """[
        {"id": "j1", "prompt": "Translate hello to French", "reference_output": "Bonjour"},
        {"prompt": "Translate goodbye to French", "reference_output": "Au revoir"}
    ]"""
    items = parse_batch_json(json_text)
    assert len(items) == 2
    assert items[0].id == "j1"
    assert items[0].prompt == "Translate hello to French"
    assert items[0].reference_output == "Bonjour"
    assert items[1].prompt == "Translate goodbye to French"


def test_parse_batch_json_nested():
    """Verify parsing JSON object with 'items' key."""
    json_text = '{"items": [{"prompt": "Test prompt", "reference_output": "Test ref"}]}'
    items = parse_batch_json(json_text)
    assert len(items) == 1
    assert items[0].prompt == "Test prompt"


@pytest.mark.asyncio
async def test_batch_lifecycle_and_processing():
    """Verify end-to-end batch creation, execution with mocked runner, and status tracking."""
    items = [
        BatchPromptItem(id="item-1", prompt="Prompt 1", reference_output="Ref 1"),
        BatchPromptItem(id="item-2", prompt="Prompt 2", reference_output="Ref 2"),
    ]
    models = [ModelID.GEMINI_3_5_FLASH]
    request = BatchUploadRequest(
        items=items,
        models=models,
        task_type=TaskType.QUESTION_ANSWERING,
    )

    batch_id = await create_batch_job(request)
    assert batch_id is not None

    status_pending = await get_batch_status(batch_id)
    assert status_pending is not None
    assert status_pending.status == "pending"
    assert status_pending.total_items == 2
    assert status_pending.completed_items == 0

    mock_run_result = EvalRunResult(
        run_id=uuid4(),
        prompt="Mock prompt",
        task_type=TaskType.QUESTION_ANSWERING,
        models=models,
        status="completed",
        responses=[
            ModelResponseSchema(
                model_id=ModelID.GEMINI_3_5_FLASH,
                output="Mock output",
                latency_ms=120.0,
                token_count=30,
            )
        ],
        scores=[
            EvalScoreSchema(
                model_id=ModelID.GEMINI_3_5_FLASH,
                bert_score_f1=0.88,
                rouge_l=0.82,
                latency_ms=120.0,
                token_count=30,
            )
        ],
        winner=ModelID.GEMINI_3_5_FLASH,
        created_at=status_pending.created_at,
    )

    with patch(
        "backend.services.batch_service.run_parallel_eval", AsyncMock(return_value=mock_run_result)
    ):
        completed_status = await process_batch_job(batch_id)
        assert completed_status.status == "completed"
        assert completed_status.completed_items == 2
        assert completed_status.failed_items == 0
        assert completed_status.completed_at is not None

    # Check results retrieval
    results_resp = await get_batch_results(batch_id)
    assert results_resp is not None
    assert len(results_resp.results) == 2
    assert results_resp.results[0].winner == ModelID.GEMINI_3_5_FLASH.value
    assert results_resp.results[0].status == "completed"

    # Check CSV export
    csv_export = await export_batch_as_csv(batch_id)
    assert "item_id,prompt,reference_output" in csv_export
    assert "item-1" in csv_export
    assert "item-2" in csv_export
    assert "gemini/gemini-3.5-flash" in csv_export
