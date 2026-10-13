"""
Модель лога действий (партиционированная таблица).
"""

from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, BigInteger, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class ActionLog(Base):
    __tablename__ = "action_logs"
    __table_args__ = {"implicit_returning": False}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    device_id = Column(UUID(as_uuid=True))
    account_id = Column(UUID(as_uuid=True))
    action_type = Column(String(50), nullable=False)
    details = Column(JSONB, default=dict)
    success = Column(Boolean, default=True)
    duration_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), primary_key=True, default=datetime.utcnow)
