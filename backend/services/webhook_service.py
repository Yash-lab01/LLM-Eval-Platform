"""Webhook Service for dispatching score threshold violation alerts."""

import hashlib
import hmac
import logging
from uuid import UUID

import httpx

from backend.schemas.eval import EvalScoreSchema
from backend.schemas.webhook import (
    WebhookAlertEvent,
    WebhookConfig,
    WebhookSeverity,
)

logger = logging.getLogger(__name__)


def compute_webhook_signature(payload_bytes: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for webhook payload validation."""
    mac = hmac.new(secret.encode("utf-8"), msg=payload_bytes, digestmod=hashlib.sha256)
    return mac.hexdigest()


async def dispatch_webhook_alert(
    url: str,
    event: WebhookAlertEvent,
    secret: str | None = None,
) -> bool:
    """Send an asynchronous HTTP POST webhook notification to a target endpoint."""
    body_json = event.model_dump_json()
    payload_bytes = body_json.encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "X-Eval-Event": event.rule_triggered,
        "X-Eval-Delivery": str(event.event_id),
    }

    if secret:
        sig = compute_webhook_signature(payload_bytes, secret)
        headers["X-Eval-Signature"] = f"sha256={sig}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, content=payload_bytes, headers=headers)
            if resp.status_code < 400:
                logger.info(f"Webhook {event.rule_triggered} dispatched successfully to {url}")
                return True
            else:
                logger.warning(
                    f"Webhook target {url} returned HTTP {resp.status_code}: {resp.text[:200]}"
                )
                return False
    except Exception as exc:
        logger.error(f"Failed to dispatch webhook alert to {url}: {exc}")
        return False


def evaluate_alert_rules(
    run_id: UUID,
    scores: list[EvalScoreSchema],
    config: WebhookConfig,
    consumer_id: str | None = None,
) -> list[WebhookAlertEvent]:
    """Inspect evaluated model scores and generate alert events for breached thresholds."""
    events: list[WebhookAlertEvent] = []

    for sc in scores:
        # Check Hallucination Risk Threshold
        if (
            sc.hallucination_score is not None
            and sc.hallucination_score >= config.hallucination_threshold
        ):
            events.append(
                WebhookAlertEvent(
                    run_id=run_id,
                    consumer_id=consumer_id,
                    severity=WebhookSeverity.WARNING,
                    rule_triggered="high_hallucination",
                    message=(
                        f"Model '{sc.model_id.value}' exceeded hallucination risk threshold: "
                        f"{sc.hallucination_score:.4f} >= {config.hallucination_threshold:.2f}"
                    ),
                    details={
                        "model_id": sc.model_id.value,
                        "hallucination_score": sc.hallucination_score,
                        "threshold": config.hallucination_threshold,
                    },
                )
            )

        # Check Latency Spike Threshold
        if sc.latency_ms >= config.latency_threshold_ms:
            events.append(
                WebhookAlertEvent(
                    run_id=run_id,
                    consumer_id=consumer_id,
                    severity=WebhookSeverity.WARNING,
                    rule_triggered="latency_spike",
                    message=(
                        f"Model '{sc.model_id.value}' exceeded latency threshold: "
                        f"{sc.latency_ms:.1f}ms >= {config.latency_threshold_ms:.1f}ms"
                    ),
                    details={
                        "model_id": sc.model_id.value,
                        "latency_ms": sc.latency_ms,
                        "threshold_ms": config.latency_threshold_ms,
                    },
                )
            )

    return events


async def check_and_dispatch_alerts(
    run_id: UUID,
    scores: list[EvalScoreSchema],
    config: WebhookConfig | None = None,
    consumer_id: str | None = None,
) -> list[WebhookAlertEvent]:
    """Evaluate alert conditions and fire webhooks if destination is configured."""
    if not config or not config.url:
        return []

    events = evaluate_alert_rules(
        run_id=run_id,
        scores=scores,
        config=config,
        consumer_id=consumer_id,
    )

    for event in events:
        await dispatch_webhook_alert(config.url, event, config.secret)

    return events
