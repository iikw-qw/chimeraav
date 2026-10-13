"""
Общие Pydantic-схемы: настройки, уведомления, планировщик, логи.
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, date


class SettingUpdate(BaseModel):
    key: str
    value: Any


class SettingResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    key: str
    value: Any
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotificationResponse(BaseModel):
    id: UUID
    user_id: UUID
    type: str
    title: str
    message: Optional[str] = None
    read: bool = False
    data: Dict[str, Any] = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class SchedulerPlanCreate(BaseModel):
    name: str
    accounts: List[str] = []
    dataset_id: Optional[UUID] = None
    frequency: Optional[str] = None
    posts_per_day: int = 1
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    caption_style: Optional[str] = None


class SchedulerPlanUpdate(BaseModel):
    name: Optional[str] = None
    accounts: Optional[List[str]] = None
    dataset_id: Optional[UUID] = None
    frequency: Optional[str] = None
    posts_per_day: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    caption_style: Optional[str] = None
    status: Optional[str] = None


class SchedulerPlanResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    accounts: List[Any] = []
    dataset_id: Optional[UUID] = None
    frequency: Optional[str] = None
    posts_per_day: int = 1
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    caption_style: Optional[str] = None
    status: str = "active"
    last_run_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ActionLogResponse(BaseModel):
    id: int
    device_id: Optional[UUID] = None
    account_id: Optional[UUID] = None
    action_type: str
    details: Dict[str, Any] = {}
    success: bool = True
    duration_ms: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    limit: int
    offset: int
