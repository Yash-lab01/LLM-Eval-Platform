"""SQLAlchemy ORM model for Prompts with version tracking."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.models.consumer import Consumer
    from backend.models.eval import EvalRun


class Prompt(Base, TimestampMixin):
    """Prompt template and test case entity with version lineage."""

    __tablename__ = "prompts"

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
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    task_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompts.id", ondelete="SET NULL"),
        nullable=True,
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=list,
        nullable=False,
    )

    # Relationships
    consumer: Mapped["Consumer | None"] = relationship(
        "Consumer",
        back_populates="prompts",
    )
    eval_runs: Mapped[list["EvalRun"]] = relationship(
        "EvalRun",
        back_populates="prompt",
    )
    parent_prompt: Mapped["Prompt | None"] = relationship(
        "Prompt",
        remote_side=[id],
    )
