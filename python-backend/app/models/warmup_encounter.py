from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from ._common import utc_now


class WarmupEncounter(Base):
    __tablename__ = "warmup_encounters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    serial: Mapped[str] = mapped_column(String(128), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    account_id: Mapped[str] = mapped_column(String(128), index=True)
    encounter_count: Mapped[int] = mapped_column(Integer, default=1)
    story_replied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
