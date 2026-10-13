"""Platform detection models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
)

from app.database import Base
from app.models._common import utc_now


class Platform(Base):
    __tablename__ = "platforms"

    id = Column(Integer, primary_key=True)
    device_serial = Column(String, index=True)
    platform_name = Column(String, nullable=False)
    package_name = Column(String, nullable=False)
    version = Column(String, nullable=True)
    version_code = Column(Integer, nullable=True)
    detected_at = Column(DateTime, default=utc_now)
    last_seen_at = Column(DateTime, nullable=True)
    is_installed = Column(Boolean, default=True)
    is_supported = Column(Boolean, default=True)
    last_warmup_at = Column(DateTime, nullable=True)
    warmup_count = Column(Integer, default=0)
    supports_posting = Column(Boolean, default=True)
    supports_stories = Column(Boolean, default=True)
    supports_reels = Column(Boolean, default=False)
    icon_path = Column(String, nullable=True)
    priority = Column(Integer, default=5)

    __table_args__ = (
        UniqueConstraint("device_serial", "package_name", name="uq_device_platform"),
    )
