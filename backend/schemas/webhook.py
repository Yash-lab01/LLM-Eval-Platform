"""Pydantic v2 schemas for Webhook notifications and score threshold alerts."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class WebhookSeverity(StrEnum):
    """Severity classification of an evaluation alert event."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class WebhookConfig(BaseModel):
    """Consumer webhook destination and threshold alert rules."""

    model_config = ConfigDict(str_strip_whitespace=True)

    url: str = Field(description="HTTPS webhook destination endpoint")
    secret: str | None = Field(
        default=None, description="Optional HMAC secret for X-Eval-Signature authentication"
    )
    hallucination_threshold: float = Field(
        default=0.40, ge=0.0, le=1.0, description="Hallucination risk threshold to trigger alert"
    )
    latency_threshold_ms: float = Field(
        default=4000.0, ge=0.0, description="Latency threshold in ms to trigger alert"
    )


class WebhookAlertEvent(BaseModel):
    """Payload dispatched to consumer webhook endpoint upon rule violation."""

    model_config = ConfigDict(from_attributes=True)

    event_id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    consumer_id: str | None = None
    severity: WebhookSeverity = WebhookSeverity.WARNING
    rule_triggered: str = Field(
        description="Triggered alert condition (e.g. 'high_hallucination', 'latency_spike')"
    )
    message: str = Field(description="Human-readable description of alert")
    details: dict = Field(
        default_factory=dict, description="Detailed metrics and model identifiers"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WebhookTestRequest(BaseModel):
    """Request payload to test webhook dispatch connectivity."""

    model_config = ConfigDict(str_strip_whitespace=True)

    target_url: str = Field(description="Target URL to send test alert to")
    secret: str | None = Field(default=None, description="Optional HMAC secret")
