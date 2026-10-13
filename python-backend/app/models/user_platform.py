"""User platform account model."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.database import Base
from app.models._common import utc_now


class UserPlatform(Base):
    __tablename__ = "user_platforms"

    id = Column(Integer, primary_key=True)
    platform_id = Column(Integer, ForeignKey("platforms.id"))
    username = Column(String, nullable=False)
    profile_id = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_logged_in = Column(Boolean, default=True)
    warmup_percent = Column(Integer, default=50)
    last_active = Column(DateTime, nullable=True)
    session_count = Column(Integer, default=0)
    default_prime_time = Column(String, nullable=True)
    timezone = Column(String, default="UTC")
