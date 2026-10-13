from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

from ._common import new_uuid, utc_now


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_gender_welcome_sent", "commenter_gender", "welcome_sent"),
        Index("ix_comments_platform_reply_status", "platform", "reply_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE")
    )
    platform: Mapped[str] = mapped_column(String(32))
    post_id_external: Mapped[str | None] = mapped_column(String(128), nullable=True)
    commenter_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commenter_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    commenter_gender: Mapped[str] = mapped_column(String(16), default="unknown")
    commenter_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    commenter_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    commenter_profile_analysis: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    comment_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reply_status: Mapped[str] = mapped_column(String(16), default="pending")
    welcome_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    welcome_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
