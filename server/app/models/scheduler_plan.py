"""
Модель плана расписания.
Зависит от: User, Dataset
"""

import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Integer, Date, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class SchedulerPlan(Base):
    __tablename__ = "scheduler_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    accounts = Column(JSONB, default=list)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="SET NULL"))
    frequency = Column(String(50))
    posts_per_day = Column(Integer, default=1)
    start_date = Column(Date)
    end_date = Column(Date)
    caption_style = Column(String(50))
    status = Column(String(20), nullable=False, default="active")
    last_run_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="scheduler_plans")
    dataset = relationship("Dataset", back_populates="scheduler_plans")
