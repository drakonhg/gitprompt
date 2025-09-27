from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    avatar_url: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    prompts: Mapped[list[Prompt]] = relationship("Prompt", back_populates="user")


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    user: Mapped[User] = relationship("User", back_populates="prompts", lazy="joined")

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    title_slug: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    visibility: Mapped[str] = mapped_column(String(20), nullable=False)
    messages: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSONB), nullable=False, default=list)
    forked_from_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("prompts.id", ondelete="SET NULL"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    forked_from: Mapped[Prompt | None] = relationship(
        "Prompt",
        remote_side="Prompt.id",
        backref="forks",
        lazy="joined",
    )

    @property
    def forked_from_prompt_title(self) -> str | None:
        return self.forked_from.title if self.forked_from else None

    @property
    def forked_from_username(self) -> str | None:
        if self.forked_from and self.forked_from.user:
            return self.forked_from.user.username
        return None

