"""Initial schema migration with core tables and indexes.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-09-23 23:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. consumers table
    op.create_table(
        "consumers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("api_key", sa.String(length=64), nullable=False, unique=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("idx_consumers_api_key", "consumers", ["api_key"], unique=True)

    # 2. prompts table
    op.create_table(
        "prompts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "consumer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("consumers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prompts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tags", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("idx_prompts_consumer_id", "prompts", ["consumer_id"])
    op.create_index("idx_prompts_task_type", "prompts", ["task_type"])

    # 3. eval_runs table
    op.create_table(
        "eval_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "consumer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("consumers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "prompt_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prompts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("models", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("reference_output", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_eval_runs_consumer", "eval_runs", ["consumer_id"])
    op.create_index("idx_eval_runs_task_type", "eval_runs", ["task_type"])
    op.create_index("idx_eval_runs_created", "eval_runs", ["created_at"])

    # 4. model_responses table
    op.create_table(
        "model_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("eval_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_id", sa.String(length=100), nullable=False),
        sa.Column("output", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("finish_reason", sa.String(length=50), server_default="stop", nullable=False),
        sa.Column("from_cache", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("attempt_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("idx_model_responses_run_id", "model_responses", ["run_id"])
    op.create_index("idx_model_responses_model_id", "model_responses", ["model_id"])

    # 5. eval_scores table
    op.create_table(
        "eval_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("eval_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_id", sa.String(length=100), nullable=False),
        sa.Column("bert_score_f1", sa.Float(), nullable=True),
        sa.Column("rouge_l", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("hallucination_score", sa.Float(), nullable=True),
        sa.Column("llm_judge_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("idx_eval_scores_run_id", "eval_scores", ["run_id"])
    op.create_index("idx_eval_scores_model", "eval_scores", ["model_id"])


def downgrade() -> None:
    op.drop_table("eval_scores")
    op.drop_table("model_responses")
    op.drop_table("eval_runs")
    op.drop_table("prompts")
    op.drop_table("consumers")
