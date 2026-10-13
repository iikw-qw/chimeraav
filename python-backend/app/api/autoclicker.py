"""AutoClicker API — start/stop automated clicking sessions."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.services.autoclicker import AutoClicker
from app.services.pc_autoclicker import PCAutoClicker

from ._deps import get_or_404, get_session

router = APIRouter(prefix="/autoclicker", tags=["autoclicker"])

_sessions: dict[str, AutoClicker | PCAutoClicker] = {}
_tasks: dict[str, asyncio.Task] = {}


class ClickVector(BaseModel):
    x: int | None = None
    y: int | None = None
    area_w: int = 20
    area_h: int = 10


class AutoClickerStart(BaseModel):
    device_id: str = ""
    button_text: str = ""
    count: int = 10
    mode: str = "photo"
    delay_min: float = 8
    delay_max: float = 13
    wait_for_completion: str | None = None
    vectors: list[ClickVector] = []
    captcha_api_key: str = ""
    target: str = "phone"  # "phone" | "pc"
    x: int | None = None
    y: int | None = None
    area_w: int = 15
    area_h: int = 10


@router.post("/start")
async def start_autoclicker(
    data: AutoClickerStart,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    task_key = data.device_id or "__pc__"

    if task_key in _tasks and not _tasks[task_key].done():
        raise HTTPException(400, "AutoClicker уже запущен")

    if data.target == "pc":
        if data.x is None or data.y is None:
            raise HTTPException(400, "Укажите координаты X и Y")
        clicker = PCAutoClicker()
        _sessions[task_key] = clicker
        task = asyncio.create_task(
            clicker.run(
                data.count, data.x, data.y,
                area_w=data.area_w, area_h=data.area_h,
                delay_min=data.delay_min, delay_max=data.delay_max,
                mode=data.mode,
            )
        )
        _tasks[task_key] = task
        return {"ok": True, "message": f"PC AutoClicker запущен ({data.count} кликов)", "mode": data.mode}

    if not data.device_id:
        raise HTTPException(400, "Выберите устройство")
    device = await get_or_404(session, Device, data.device_id)
    serial = device.serial or device.id

    clicker = AutoClicker(serial, data.captcha_api_key)
    _sessions[task_key] = clicker
    vectors = [v.model_dump() for v in data.vectors] if data.vectors else None

    if data.mode == "sequential":
        task = asyncio.create_task(
            clicker.run_sequential_mode(
                data.button_text, data.count,
                wait_for_completion=data.wait_for_completion,
                vectors=vectors,
            )
        )
    else:
        task = asyncio.create_task(
            clicker.run_photo_mode(
                data.button_text, data.count,
                delay_min=data.delay_min, delay_max=data.delay_max,
                vectors=vectors,
            )
        )
    _tasks[task_key] = task

    return {"ok": True, "message": f"AutoClicker запущен на {device.name}", "mode": data.mode}


@router.post("/stop")
async def stop_autoclicker(device_id: str = "__pc__") -> dict:
    clicker = _sessions.get(device_id)
    if clicker:
        clicker.stop()
    task = _tasks.pop(device_id, None)
    if task and not task.done():
        task.cancel()
    _sessions.pop(device_id, None)
    return {"ok": True}


@router.get("/status")
async def autoclicker_status(device_id: str = "__pc__") -> dict:
    task = _tasks.get(device_id)
    if not task:
        return {"running": False}
    if task.done():
        try:
            result = task.result()
        except Exception as e:
            return {"running": False, "error": str(e)}
        return {"running": False, "result": result}
    return {"running": True}


@router.get("/mouse-position")
async def get_mouse_position() -> dict:
    return PCAutoClicker.get_mouse_position()
