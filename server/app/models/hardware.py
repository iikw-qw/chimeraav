"""
Модели лицензий привязанных к железу и метрик хоста.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Boolean, Integer, BigInteger, Float, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class HardwareLicense(Base):
    __tablename__ = "hardware_licenses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    hardware_id = Column(String(255), nullable=False, unique=True)
    hostname = Column(String(200))
    os_name = Column(String(50))
    os_version = Column(String(50))
    cpu_info = Column(String(200))
    ram_gb = Column(Integer)
    mac_address = Column(String(50))
    first_seen_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_seen_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class HostMetric(Base):
    __tablename__ = "host_metrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    hardware_id = Column(String(255))
    cpu_percent = Column(Float)
    ram_percent = Column(Float)
    disk_percent = Column(Float)
    network_sent_mb = Column(Float)
    network_recv_mb = Column(Float)
    uptime_seconds = Column(BigInteger)
    active_devices = Column(Integer, default=0)
    recorded_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("idx_metrics_hw", "hardware_id", "recorded_at"),
    )
