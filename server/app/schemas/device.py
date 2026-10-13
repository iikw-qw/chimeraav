"""
Pydantic-схемы для устройств.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class DeviceCreate(BaseModel):
    name: str = Field(max_length=100)
    device_type: str = Field(pattern="^(android|ios)$")
    serial_number: Optional[str] = None
    ip_address: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    os_version: Optional[str] = None


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    ip_address: Optional[str] = None
    external_ip: Optional[str] = None
    vpn_active: Optional[bool] = None
    proxy_info: Optional[Dict[str, Any]] = None
    battery_level: Optional[int] = None
    temperature: Optional[float] = None
    screen_resolution: Optional[str] = None
    ram_mb: Optional[int] = None


class DeviceResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    device_type: str
    serial_number: Optional[str] = None
    ip_address: Optional[str] = None
    external_ip: Optional[str] = None
    vpn_active: bool = False
    proxy_info: Dict[str, Any] = {}
    status: str = "offline"
    battery_level: Optional[int] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    os_version: Optional[str] = None
    screen_resolution: Optional[str] = None
    ram_mb: Optional[int] = None
    temperature: Optional[float] = None
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
