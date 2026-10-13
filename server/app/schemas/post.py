"""
Pydantic-схемы для постов и датасетов.
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime


class PostCreate(BaseModel):
    account_id: Optional[UUID] = None
    dataset_id: Optional[UUID] = None
    photos: List[str] = []
    caption: Optional[str] = None
    platform: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class PostUpdate(BaseModel):
    caption: Optional[str] = None
    status: Optional[str] = None
    photos: Optional[List[str]] = None
    scheduled_at: Optional[datetime] = None


class PostResponse(BaseModel):
    id: UUID
    user_id: UUID
    account_id: Optional[UUID] = None
    dataset_id: Optional[UUID] = None
    photos: List[Any] = []
    caption: Optional[str] = None
    platform: Optional[str] = None
    status: str = "draft"
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    engagement: Dict[str, Any] = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class DatasetCreate(BaseModel):
    name: str
    photos: List[str] = []


class DatasetResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    photos: List[Any] = []
    total_photos: int = 0
    usage_stats: Dict[str, Any] = {}
    created_at: datetime

    model_config = {"from_attributes": True}
