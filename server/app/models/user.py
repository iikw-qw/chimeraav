"""
Модель пользователя системы Chimera.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, BigInteger, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    telegram_username = Column(String(100))
    telegram_id = Column(BigInteger)
    telegram_verified = Column(Boolean, default=False)
    verification_code = Column(String(6))
    app_version = Column(String(20))
    hardware_id = Column(String(255))
    is_active = Column(Boolean, default=True)
    onboarding_completed = Column(Boolean, default=False)
    last_login_at = Column(DateTime(timezone=True))
    login_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    accounts = relationship("SocialAccount", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="user", cascade="all, delete-orphan")
    datasets = relationship("Dataset", back_populates="user", cascade="all, delete-orphan")
    scheduler_plans = relationship("SchedulerPlan", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
