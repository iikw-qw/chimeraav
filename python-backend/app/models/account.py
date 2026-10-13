from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

from ._common import gen_account_code, new_uuid, utc_now


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    unique_code: Mapped[str | None] = mapped_column(
        String(24), unique=True, nullable=True, default=gen_account_code
    )
    device_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("devices.id", ondelete="CASCADE")
    )
    platform: Mapped[str] = mapped_column(String(32))
    username: Mapped[str] = mapped_column(String(255))
    password_encrypted: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    posting_style: Mapped[str] = mapped_column(String(32), default="friendly")
    auto_reply_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    welcome_message_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_chatter_language: Mapped[str] = mapped_column(String(8), default="en")
    notify_new_messages: Mapped[bool] = mapped_column(Boolean, default=False)
    activity_hours_min: Mapped[int] = mapped_column(Integer, default=1)
    activity_hours_max: Mapped[int] = mapped_column(Integer, default=6)
    warmup_stage: Mapped[int] = mapped_column(Integer, default=0)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email_password_encrypted: Mapped[str | None] = mapped_column(String(512), nullable=True)
    email_imap_server: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
