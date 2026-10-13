"""Content uniqueization + app cloning endpoints."""

from __future__ import annotations

import os
import tempfile
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.services.app_cloner import AppCloner
from app.services.content_uniqueizer import ContentUniqueizer

from ._deps import get_or_404, get_session

router = APIRouter(prefix="/content", tags=["content"])


class UniqueizeIn(BaseModel):
    file_path: str
    type: str = "photo"


@router.post("/uniqueize")
async def uniqueize(payload: UniqueizeIn) -> dict:
    if not os.path.isfile(payload.file_path):
        raise HTTPException(404, "Файл не найден")
    ext = ".jpg" if payload.type == "photo" else ".mp4"
    fd, out_path = tempfile.mkstemp(suffix=f"_unique{ext}")
    os.close(fd)
    u = ContentUniqueizer()
    if payload.type == "photo":
        result = u.uniqueize_photo(payload.file_path, out_path)
    else:
        result = u.uniqueize_video(payload.file_path, out_path)
    if "error" in result:
        raise HTTPException(500, result["error"])
    return result


class CloneAppIn(BaseModel):
    package: str
    clone_index: int = 1


@router.post("/devices/{device_id}/clone-app")
async def clone_app(
    device_id: str,
    payload: CloneAppIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    device = await get_or_404(session, Device, device_id)
    if not device.serial:
        raise HTTPException(400, "У устройства нет serial")
    cloner = AppCloner(device.serial)
    return await cloner.create_clone(payload.package, payload.clone_index)


@router.get("/devices/{device_id}/clones")
async def list_clones(
    device_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict]:
    device = await get_or_404(session, Device, device_id)
    if not device.serial:
        raise HTTPException(400, "У устройства нет serial")
    cloner = AppCloner(device.serial)
    return await cloner.list_clones()
