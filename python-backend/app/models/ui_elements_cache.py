from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

from ._common import new_uuid, utc_now


class UIElementsCache(Base):
    __tablename__ = "ui_elements_cache"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    platform: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(32))
    os_type: Mapped[str] = mapped_column(String(16))
    os_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    locators: Mapped[str] = mapped_column(Text, default="{}")
    screenshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
