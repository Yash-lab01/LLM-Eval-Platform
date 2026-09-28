"""Integration tests for Phase 7A REST APIs: Rubrics, LLM Judge, Batch Eval, and Regression Suites."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.schemas.consumers import TaskType
from backend.schemas.eval import EvalRunResult, EvalScoreSchema, ModelResponseSchema
from backend.schemas.models import ModelID


@pytest.fixture
def mock_eval_run_result():
    """Sample successful EvalRunResult fixture."""
    return EvalRunResult(
        run_id=uuid4(),
        prompt="Sample prompt",
        task_type=TaskType.QUESTION_ANSWERING,
        models=[ModelID.GEMINI_3_5_FLASH],
        status="completed",
        responses=[
            ModelResponseSchema(
                model_id=ModelID.GEMINI_3_5_FLASH,
                output="Valid model output",
                latency_ms=150.0,
                token_count=35,
            )
        ],
        scores=[
            EvalScoreSchema(
                model_id=ModelID.GEMINI_3_5_FLASH,
                bert_score_f1=0.85,
                rouge_l=0.80,
                llm_judge_score=0.90,
                latency_ms=150.0,
                token_count=35,
            )
        ],
        winner=ModelID.GEMINI_3_5_FLASH,
        created_at="2026-09-28T00:00:00Z",
    )


@pytest.mark.asyncio
async def test_rubrics_api_endpoints():
    """Verify GET, POST, and judge endpoints on /api/v1/rubrics."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. GET all rubrics
        resp = await ac.get("/api/v1/rubrics")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 8
        assert any(r["task_type"] == "code_generation" for r in data)

        # 2. GET single rubric
        resp_single = await ac.get("/api/v1/rubrics/code_generation")
        assert resp_single.status_code == 200
        single_data = resp_single.json()
        assert single_data["task_type"] == "code_generation"
        assert len(single_data["criteria"]) >= 1

        # 3. POST custom rubric
        custom_payload = {
            "task_type": "translation",
            "title": "API Test Custom Translation Rubric",
            "description": "High fidelity translation rubric",
            "criteria": [
                {
                    "name": "grammar_accuracy",
                    "weight": 0.6,
                    "description": "Grammatical precision in target language",
                },
                {
                    "name": "cultural_fit",
                    "weight": 0.4,
                    "description": "Natural idiom and cultural appropriateness",
                },
            ],
        }
        resp_create = await ac.post("/api/v1/rubrics", json=custom_payload)
        assert resp_create.status_code == 201
        created_data = resp_create.json()
        assert created_data["title"] == "API Test Custom Translation Rubric"

        # 4. POST judge response
        judge_req = {
            "prompt": "What is Python?",
            "model_output": "Python is a high-level programming language.",
            "task_type": "question_answering",
        }
        resp_judge = await ac.post("/api/v1/rubrics/judge", json=judge_req)
        assert resp_judge.status_code == 200
        judge_data = resp_judge.json()
        assert "overall_score" in judge_data
        assert "criterion_scores" in judge_data
        assert "reasoning" in judge_data


@pytest.mark.asyncio
async def test_batch_api_endpoints(mock_eval_run_result):
    """Verify batch upload, progress, results, and CSV export on /api/v1/batch."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. POST JSON batch create
        batch_payload = {
            "items": [
                {"prompt": "Calculate 2+2", "reference_output": "4"},
                {"prompt": "Calculate 10*5", "reference_output": "50"},
            ],
            "models": ["gemini/gemini-3.5-flash"],
            "task_type": "question_answering",
        }

        with patch(
            "backend.services.batch_service.run_parallel_eval",
            AsyncMock(return_value=mock_eval_run_result),
        ):
            create_resp = await ac.post("/api/v1/batch/create", json=batch_payload)
            assert create_resp.status_code == 202
            batch_id = create_resp.json()["batch_id"]

            # 2. GET batch status
            status_resp = await ac.get(f"/api/v1/batch/{batch_id}")
            assert status_resp.status_code == 200
            assert status_resp.json()["total_items"] == 2

            # 3. GET batch results
            results_resp = await ac.get(f"/api/v1/batch/{batch_id}/results")
            assert results_resp.status_code == 200
            assert "results" in results_resp.json()

            # 4. GET batch CSV export
            export_resp = await ac.get(f"/api/v1/batch/{batch_id}/export")
            assert export_resp.status_code == 200
            assert "text/csv" in export_resp.headers.get("content-type", "")
            assert "item_id,prompt,reference_output" in export_resp.text

        # 5. POST upload CSV file
        csv_file_content = b"prompt,reference_output\nHello world,Greeting\nGoodbye,Farewell\n"
        files = {"file": ("test.csv", csv_file_content, "text/csv")}
        data = {"models": "gemini/gemini-3.5-flash", "task_type": "question_answering"}

        with patch(
            "backend.services.batch_service.run_parallel_eval",
            AsyncMock(return_value=mock_eval_run_result),
        ):
            upload_resp = await ac.post("/api/v1/batch/upload-file", files=files, data=data)
            assert upload_resp.status_code == 202
            assert upload_resp.json()["total_items"] == 2


@pytest.mark.asyncio
async def test_suites_api_endpoints(mock_eval_run_result):
    """Verify prompt suite CRUD, execution, and regression delta report on /api/v1/suites."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. POST create suite
        suite_payload = {
            "name": "Integration Benchmark Suite",
            "description": "Full end-to-end API test suite",
            "task_type": "question_answering",
            "prompts": [
                {"id": "p1", "prompt": "Prompt A", "reference_output": "Ref A"},
                {"id": "p2", "prompt": "Prompt B", "reference_output": "Ref B"},
            ],
        }
        create_resp = await ac.post("/api/v1/suites", json=suite_payload)
        assert create_resp.status_code == 201
        suite_id = create_resp.json()["id"]

        # 2. GET all suites
        all_resp = await ac.get("/api/v1/suites")
        assert all_resp.status_code == 200
        assert any(s["id"] == suite_id for s in all_resp.json())

        # 3. GET single suite
        get_resp = await ac.get(f"/api/v1/suites/{suite_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Integration Benchmark Suite"

        with patch(
            "backend.services.suite_service.run_parallel_eval",
            AsyncMock(return_value=mock_eval_run_result),
        ):
            # 4. POST run suite (run 1: baseline)
            run_resp_1 = await ac.post(
                f"/api/v1/suites/{suite_id}/run",
                json={"models": ["gemini/gemini-3.5-flash"]},
            )
            assert run_resp_1.status_code == 200
            run_id_1 = run_resp_1.json()["run_id"]

            # 5. POST run suite (run 2: candidate)
            run_resp_2 = await ac.post(
                f"/api/v1/suites/{suite_id}/run",
                json={"models": ["gemini/gemini-3.5-flash"]},
            )
            assert run_resp_2.status_code == 200
            run_id_2 = run_resp_2.json()["run_id"]

            # 6. GET suite runs
            runs_resp = await ac.get(f"/api/v1/suites/{suite_id}/runs")
            assert runs_resp.status_code == 200
            assert len(runs_resp.json()) >= 2

            # 7. GET regression report
            report_resp = await ac.get(
                f"/api/v1/suites/{suite_id}/regression-report",
                params={"baseline_run_id": run_id_1, "candidate_run_id": run_id_2},
            )
            assert report_resp.status_code == 200
            report_data = report_resp.json()
            assert report_data["suite_id"] == suite_id
            assert report_data["baseline_run_id"] == run_id_1
            assert report_data["candidate_run_id"] == run_id_2
            assert report_data["total_prompts"] == 2
            assert "deltas" in report_data
