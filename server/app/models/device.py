"""
Модель устройства (Android/iOS).
Зависит от: User
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, SmallInteger, Integer, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    device_type = Column(String(10), nullable=False)
    serial_number = Column(String(100), unique=True)
    ip_address = Column(INET)
    external_ip = Column(String(45))
    vpn_active = Column(Boolean, default=False)
    proxy_info = Column(JSONB, default=dict)
    status = Column(String(20), nullable=False, default="offline")
    battery_level = Column(SmallInteger)
    model = Column(String(100))
    manufacturer = Column(String(100))
    os_version = Column(String(50))
    screen_resolution = Column(String(20))
    ram_mb = Column(Integer)
    temperature = Column(Float)
    last_seen_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="devices")
    accounts = relationship("SocialAccount", back_populates="device")
    tasks = relationship("Task", back_populates="device")
