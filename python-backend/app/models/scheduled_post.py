"""Scheduled post model."""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
)
from sqlalchemy.types import JSON

from app.database import Base
from app.models._common import utc_now


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"

    id = Column(Integer, primary_key=True)
    user_platform_id = Column(Integer, ForeignKey("user_platforms.id"), nullable=True)
    device_serial = Column(String, nullable=False)
    platform = Column(String, nullable=False)
    media_files = Column(JSON)
    media_count = Column(Integer, nullable=True)
    is_mixed = Column(Boolean, default=True)
    is_uniqueized = Column(Boolean, default=True)
    caption = Column(String, nullable=True)
    caption_style = Column(String, nullable=True)
    hashtags = Column(JSON, nullable=True)
    location = Column(String, nullable=True)
    mentions = Column(JSON, nullable=True)
    scheduled_date = Column(Date, nullable=False)
    scheduled_time = Column(Time, nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    timezone = Column(String, default="UTC")
    is_prime_time = Column(Boolean, default=False)
    status = Column(String, default="pending")
    retry_count = Column(Integer, default=0)
    last_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, nullable=True)
    account_mapping_id = Column(Integer, ForeignKey("account_mappings.id"), nullable=True)
    posted_at = Column(DateTime, nullable=True)
