"""Unit tests for Webhook Service: signature calculation, rule evaluation, and dispatching."""

import hashlib
import hmac
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from backend.schemas.eval import EvalScoreSchema
from backend.schemas.models import ModelID
from backend.schemas.webhook import (
    WebhookAlertEvent,
    WebhookConfig,
    WebhookSeverity,
)
from backend.services.webhook_service import (
    compute_webhook_signature,
    dispatch_webhook_alert,
    evaluate_alert_rules,
)


def test_compute_webhook_signature():
    """Verify HMAC-SHA256 signature computation matches standard hmac output."""
    secret = "test-secret-key-123"
    payload = b'{"event": "test", "status": "ok"}'

    sig = compute_webhook_signature(payload, secret)
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    assert sig == expected


def test_evaluate_alert_rules_triggers_hallucination_and_latency():
    """Verify alert rules detect threshold breaches for hallucination and latency."""
    config = WebhookConfig(
        url="https://consumer.example.com/alerts",
        hallucination_threshold=0.40,
        latency_threshold_ms=3000.0,
    )

    scores = [
        EvalScoreSchema(
            model_id=ModelID.GEMINI_3_5_FLASH,
            hallucination_score=0.10,
            latency_ms=1500.0,
            token_count=30,
        ),
        EvalScoreSchema(
            model_id=ModelID.GROQ_GPT_OSS_120B,
            hallucination_score=0.65,  # breaches threshold 0.40
            latency_ms=4200.0,  # breaches threshold 3000.0
            token_count=30,
        ),
    ]

    events = evaluate_alert_rules(
        run_id=uuid4(),
        scores=scores,
        config=config,
        consumer_id="consumer-abc",
    )

    assert len(events) == 2
    rule_types = {e.rule_triggered for e in events}
    assert "high_hallucination" in rule_types
    assert "latency_spike" in rule_types
    assert all(e.severity == WebhookSeverity.WARNING for e in events)


def test_evaluate_alert_rules_healthy():
    """Verify no alerts generated when all scores fall within thresholds."""
    config = WebhookConfig(
        url="https://consumer.example.com/alerts",
        hallucination_threshold=0.50,
        latency_threshold_ms=5000.0,
    )

    scores = [
        EvalScoreSchema(
            model_id=ModelID.GEMINI_3_5_FLASH,
            hallucination_score=0.05,
            latency_ms=250.0,
            token_count=20,
        )
    ]

    events = evaluate_alert_rules(run_id=uuid4(), scores=scores, config=config)
    assert len(events) == 0


@pytest.mark.asyncio
async def test_dispatch_webhook_alert_success():
    """Verify dispatch_webhook_alert sends POST request with HMAC signature header."""
    event = WebhookAlertEvent(
        run_id=uuid4(),
        rule_triggered="high_hallucination",
        message="Critical hallucination detected",
    )

    mock_resp = AsyncMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp)) as mock_post:
        success = await dispatch_webhook_alert(
            url="https://webhook.site/test",
            event=event,
            secret="my-secret",
        )
        assert success is True
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert "X-Eval-Signature" in kwargs["headers"]
        assert kwargs["headers"]["X-Eval-Signature"].startswith("sha256=")
