"""
Pydantic-схемы для задач.
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class TaskCreate(BaseModel):
    device_id: Optional[UUID] = None
    account_id: Optional[UUID] = None
    task_type: str
    priority: int = 5
    payload: Dict[str, Any] = {}
    scheduled_at: Optional[datetime] = None
    max_retries: int = 3


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class TaskResponse(BaseModel):
    id: UUID
    user_id: UUID
    device_id: Optional[UUID] = None
    account_id: Optional[UUID] = None
    task_type: str
    status: str = "pending"
    priority: int = 5
    payload: Dict[str, Any] = {}
    result: Dict[str, Any] = {}
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
