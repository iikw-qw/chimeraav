"""
Pydantic-схемы для пользователей и авторизации.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    telegram_username: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    telegram_username: Optional[str] = None
    telegram_id: Optional[int] = None
    telegram_verified: bool = False
    app_version: Optional[str] = None
    is_active: bool = True
    onboarding_completed: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    verification_code: Optional[str] = None
    hardware_id: Optional[str] = None


class VerifyTelegramRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    telegram_id: Optional[int] = None
    telegram_username: Optional[str] = None
