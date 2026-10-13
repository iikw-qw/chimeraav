from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from ._common import utc_now


class AuthorizedDevice(Base):
    __tablename__ = "authorized_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hwid: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    chat_id: Mapped[str] = mapped_column(String(64))
    label: Mapped[str | None] = mapped_column(String(256), nullable=True)
    authorized_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
