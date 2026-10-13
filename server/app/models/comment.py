"""
Модель отслеживаемого комментария.
Зависит от: SocialAccount
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class TrackedComment(Base):
    __tablename__ = "tracked_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("social_accounts.id", ondelete="CASCADE"))
    platform = Column(String(20), nullable=False)
    post_url = Column(Text)
    commenter_username = Column(String(255))
    commenter_user_id = Column(String(255))
    commenter_gender = Column(String(10))
    commenter_country = Column(String(100))
    commenter_analysis = Column(JSONB, default=dict)
    comment_text = Column(Text)
    response_status = Column(String(20), default="pending")
    response_text = Column(Text)
    response_style = Column(String(20))
    response_scheduled_at = Column(DateTime(timezone=True))
    response_sent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    account = relationship("SocialAccount", back_populates="comments")
