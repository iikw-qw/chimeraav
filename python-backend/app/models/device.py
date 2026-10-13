from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

from ._common import gen_device_code, new_uuid, utc_now


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    unique_code: Mapped[str | None] = mapped_column(
        String(24), unique=True, nullable=True, default=gen_device_code
    )
    name: Mapped[str] = mapped_column(String(255))
    platform: Mapped[str] = mapped_column(String(16))  # android | ios
    status: Mapped[str] = mapped_column(String(16), default="offline")
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    serial: Mapped[str | None] = mapped_column(String(128), nullable=True)
    battery_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proxy_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("proxies.id", ondelete="SET NULL"), nullable=True
    )
    group_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_master: Mapped[bool] = mapped_column(Boolean, default=False)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
