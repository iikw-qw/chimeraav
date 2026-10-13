"""
Модель задачи (пост, лайк, прогрев и т.д.).
Зависит от: User, Device, SocialAccount
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, SmallInteger, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"))
    account_id = Column(UUID(as_uuid=True), ForeignKey("social_accounts.id", ondelete="SET NULL"))
    task_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    priority = Column(SmallInteger, default=5)
    payload = Column(JSONB, default=dict)
    result = Column(JSONB, default=dict)
    error_message = Column(Text)
    retry_count = Column(SmallInteger, default=0)
    max_retries = Column(SmallInteger, default=3)
    scheduled_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="tasks")
    device = relationship("Device", back_populates="tasks")
    account = relationship("SocialAccount", back_populates="tasks")
