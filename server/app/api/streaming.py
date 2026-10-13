"""
REST API для стримов устройств.
З��висит от: redis_client, deps
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from app.models.user import User
from app.api.deps import get_current_user
from app.services.redis_client import redis_client

router = APIRouter()


@router.get("")
async def list_streams(current_user: User = Depends(get_current_user)):
    streams = await redis_client.hgetall("chimera:active_streams")
    return {"streams": streams}


@router.get("/{device_id}")
async def get_stream_info(device_id: UUID, current_user: User = Depends(get_current_user)):
    info = await redis_client.hget("chimera:active_streams", str(device_id))
    if not info:
        raise HTTPException(status_code=404, detail="Stream not found")
    return info


@router.post("/{device_id}/screenshot")
async def request_screenshot(device_id: UUID, current_user: User = Depends(get_current_user)):
    await redis_client.publish(f"device:{device_id}:commands", {"type": "screenshot"})
    return {"message": "Screenshot requested", "device_id": str(device_id)}
