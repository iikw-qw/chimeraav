"""
Модель аккаунта соцсети.
Зависит от: User, Device
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"))
    platform = Column(String(20), nullable=False)
    username = Column(String(255), nullable=False)
    password_encrypted = Column(String(512))
    display_name = Column(String(255))
    status = Column(String(20), nullable=False, default="active")
    proxy_url = Column(String(500))
    email = Column(String(200))
    email_password_encrypted = Column(String(512))
    followers_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    posts_count = Column(Integer, default=0)
    warmup_enabled = Column(Boolean, default=False)
    login_status = Column(String(20), default="logged_out")
    last_login_at = Column(DateTime(timezone=True))
    last_activity_at = Column(DateTime(timezone=True))
    session_cookies = Column(String(4096))
    login_attempts = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("platform", "username", name="uq_platform_username"),)

    user = relationship("User", back_populates="accounts")
    device = relationship("Device", back_populates="accounts")
    tasks = relationship("Task", back_populates="account")
    posts = relationship("Post", back_populates="account")
    comments = relationship("TrackedComment", back_populates="account")
