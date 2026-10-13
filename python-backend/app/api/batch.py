from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.task import Task

from ._deps import get_session

router = APIRouter(prefix="/batch", tags=["batch"])


class BatchActionPayload(BaseModel):
    device_ids: list[str] | None = None
    group_name: str | None = None
    action: str  # e.g. "restart", "warmup_step", "publish", "stop"
    payload: dict[str, Any] | None = None
    priority: int = 5


@router.post("/action")
async def batch_action(
    payload: BatchActionPayload,
    background: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    stmt = select(Device)
    if payload.device_ids:
        stmt = stmt.where(Device.id.in_(payload.device_ids))
    elif payload.group_name:
        stmt = stmt.where(Device.group_name == payload.group_name)
    devices = list((await session.execute(stmt)).scalars().all())

    tasks: list[Task] = []
    for d in devices:
        tasks.append(
            Task(
                device_id=d.id,
                task_type=payload.action,
                status="pending",
                priority=payload.priority,
                payload=payload.payload,
            )
        )
    session.add_all(tasks)
    await session.commit()
    background.add_task(_announce_batch, payload.action, len(tasks))
    return {
        "action": payload.action,
        "device_count": len(devices),
        "tasks_created": len(tasks),
    }


async def _announce_batch(action: str, count: int) -> None:
    from ._hub import hub

    await hub.broadcast(
        "tasks",
        {"event": "batch_dispatched", "action": action, "count": count},
    )


class SyncPayload(BaseModel):
    device_ids: list[str] | None = None


@router.post("/sync")
async def batch_sync(
    payload: SyncPayload, session: Annotated[AsyncSession, Depends(get_session)]
) -> dict:
    stmt = select(Device)
    if payload.device_ids:
        stmt = stmt.where(Device.id.in_(payload.device_ids))
    devices = list((await session.execute(stmt)).scalars().all())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for d in devices:
        d.last_heartbeat = now
    await session.commit()
    return {"synced": len(devices), "at": now.isoformat()}
