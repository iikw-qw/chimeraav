from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from ._common import utc_now


class WarmupWhitelist(Base):
    __tablename__ = "warmup_whitelist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    boost_factor: Mapped[float] = mapped_column(Float, default=2.0)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
