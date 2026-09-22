"""Celery Application Initialization.

Configures Celery broker (Redis DB 1) and result backend (Redis DB 2) per ADR-003.
Defines task routing for eval_default and eval_batch queues.
"""

from celery import Celery

from backend.core.config import settings

celery_app = Celery(
    "llm_eval_platform",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue="eval_default",
    task_routes={
        "backend.tasks.eval_tasks.run_eval_task": {"queue": "eval_default"},
        "backend.tasks.eval_tasks.run_batch_eval_task": {"queue": "eval_batch"},
    },
)
