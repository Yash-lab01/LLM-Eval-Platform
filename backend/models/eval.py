"""SQLAlchemy ORM models for Evaluation Runs, Model Responses, and Computed Scores."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.models.consumer import Consumer
    from backend.models.prompt import Prompt


class EvalRun(Base, TimestampMixin):
    """Execution run tracking a prompt sent across multiple benchmarked models."""

    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    consumer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consumers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    prompt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompts.id", ondelete="SET NULL"),
        nullable=True,
    )
    prompt_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    task_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    models: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
    )
    reference_output: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    consumer: Mapped["Consumer | None"] = relationship(
        "Consumer",
        back_populates="eval_runs",
    )
    prompt: Mapped["Prompt | None"] = relationship(
        "Prompt",
        back_populates="eval_runs",
    )
    responses: Mapped[list["ModelResponseORM"]] = relationship(
        "ModelResponseORM",
        back_populates="eval_run",
        cascade="all, delete-orphan",
    )
    scores: Mapped[list["EvalScoreORM"]] = relationship(
        "EvalScoreORM",
        back_populates="eval_run",
        cascade="all, delete-orphan",
    )


class ModelResponseORM(Base, TimestampMixin):
    """Raw model generation output and telemetry for an individual model."""

    __tablename__ = "model_responses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    output: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    finish_reason: Mapped[str] = mapped_column(
        String(50),
        default="stop",
        nullable=False,
    )
    from_cache: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # Relationships
    eval_run: Mapped["EvalRun"] = relationship(
        "EvalRun",
        back_populates="responses",
    )


class EvalScoreORM(Base, TimestampMixin):
    """Evaluation metrics calculated for a single model's response."""

    __tablename__ = "eval_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    bert_score_f1: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    rouge_l: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    estimated_cost_usd: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    hallucination_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    llm_judge_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # Relationships
    eval_run: Mapped["EvalRun"] = relationship(
        "EvalRun",
        back_populates="scores",
    )
