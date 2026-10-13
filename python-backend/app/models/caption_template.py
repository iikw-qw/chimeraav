from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

from ._common import new_uuid, utc_now


class CaptionTemplate(Base):
    __tablename__ = "caption_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    category: Mapped[str] = mapped_column(String(100), default="general")
    text: Mapped[str] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(String(30), default="instagram")
    language: Mapped[str] = mapped_column(String(10), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
