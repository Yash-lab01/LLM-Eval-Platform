"""SQLAlchemy ORM model for Consumers."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.models.eval import EvalRun
    from backend.models.prompt import Prompt


class Consumer(Base, TimestampMixin):
    """Registered consumer application or agent utilizing the evaluation platform."""

    __tablename__ = "consumers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    api_key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    # Relationships
    prompts: Mapped[list["Prompt"]] = relationship(
        "Prompt",
        back_populates="consumer",
        cascade="all, delete-orphan",
    )
    eval_runs: Mapped[list["EvalRun"]] = relationship(
        "EvalRun",
        back_populates="consumer",
    )
