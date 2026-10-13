"""Account-to-device mapping for multi-account warmup."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Integer, String, UniqueConstraint

from app.database import Base
from app.models._common import utc_now


class AccountMapping(Base):
    __tablename__ = "account_mappings"

    id = Column(Integer, primary_key=True)
    serial = Column(String, index=True, nullable=False)
    platform = Column(String, nullable=False)
    username = Column(String, nullable=False)
    package_name = Column(String, nullable=False)
    user_id = Column(Integer, default=0)
    clone_method = Column(String, nullable=True)
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)

    __table_args__ = (
        UniqueConstraint("serial", "platform", "username", name="uq_account_map"),
    )
