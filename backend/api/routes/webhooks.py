"""API routes for Webhook alert notifications and delivery testing."""

import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.schemas.eval import EvalScoreSchema
from backend.schemas.webhook import (
    WebhookAlertEvent,
    WebhookConfig,
    WebhookSeverity,
    WebhookTestRequest,
)
from backend.services.webhook_service import (
    check_and_dispatch_alerts,
    dispatch_webhook_alert,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhook Alerts"])


class WebhookCheckRequest(BaseModel):
    """Payload to evaluate scores against webhook alert thresholds."""

    run_id: str
    scores: list[EvalScoreSchema]
    config: WebhookConfig


@router.post("/test", status_code=status.HTTP_200_OK)
async def test_webhook_endpoint(request: WebhookTestRequest) -> dict:
    """Send a sample test alert event to verify webhook receiver connectivity."""
    test_event = WebhookAlertEvent(
        event_id=uuid4(),
        run_id=uuid4(),
        consumer_id="test-consumer",
        severity=WebhookSeverity.INFO,
        rule_triggered="test_ping",
        message="This is a test alert verifying webhook delivery connectivity.",
        details={"ping": "pong", "platform": "LLM-Eval-Platform"},
    )

    success = await dispatch_webhook_alert(
        url=request.target_url,
        event=test_event,
        secret=request.secret,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Webhook delivery failed for target URL: {request.target_url}",
        )

    return {
        "status": "delivered",
        "target_url": request.target_url,
        "event_id": str(test_event.event_id),
    }


@router.post("/check", status_code=status.HTTP_200_OK)
async def check_webhook_thresholds(request: WebhookCheckRequest) -> dict:
    """Evaluate evaluated scores against threshold rules and dispatch any triggered alerts."""
    from uuid import UUID

    events = await check_and_dispatch_alerts(
        run_id=UUID(request.run_id),
        scores=request.scores,
        config=request.config,
    )

    return {
        "alerts_triggered_count": len(events),
        "events": [e.model_dump(mode="json") for e in events],
    }
