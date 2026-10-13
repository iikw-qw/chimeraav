"""
Pydantic-схемы для аккаунтов соцсетей.
"""

from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class AccountCreate(BaseModel):
    platform: str
    username: str = Field(max_length=255)
    password_encrypted: Optional[str] = None
    display_name: Optional[str] = None
    device_id: Optional[UUID] = None
    proxy_url: Optional[str] = None


class AccountUpdate(BaseModel):
    device_id: Optional[UUID] = None
    display_name: Optional[str] = None
    status: Optional[str] = None
    proxy_url: Optional[str] = None
    warmup_enabled: Optional[bool] = None
    login_status: Optional[str] = None
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    posts_count: Optional[int] = None


class AccountResponse(BaseModel):
    id: UUID
    user_id: UUID
    device_id: Optional[UUID] = None
    platform: str
    username: str
    password_encrypted: Optional[str] = None
    display_name: Optional[str] = None
    status: str = "active"
    proxy_url: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    warmup_enabled: bool = False
    login_status: str = "logged_out"
    last_activity_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
