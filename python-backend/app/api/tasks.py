from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task

from ._deps import apply_update, get_or_404, get_session

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    device_id: str
    account_id: str | None = None
    task_type: str
    status: str = "pending"
    priority: int = 5
    payload: dict[str, Any] | None = None
    max_retries: int = 3
    scheduled_at: datetime | None = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    priority: int | None = None
    payload: dict[str, Any] | None = None
    error_message: str | None = None
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class TaskRead(TaskBase):
    id: str
    retry_count: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    session: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    device_id: str | None = None,
    task_type: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
) -> list[Task]:
    stmt = select(Task)
    if status:
        stmt = stmt.where(Task.status == status)
    if device_id:
        stmt = stmt.where(Task.device_id == device_id)
    if task_type:
        stmt = stmt.where(Task.task_type == task_type)
    stmt = stmt.order_by(Task.created_at.desc()).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


@router.post("", response_model=TaskRead, status_code=201)
async def create_task(
    payload: TaskCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> Task:
    task = Task(**payload.model_dump())
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


class BatchScheduleIn(BaseModel):
    device_ids: list[str]
    account_id: str | None = None
    dataset_id: str
    platform: str = "instagram"
    days: int = 7
    posts_per_day: int = 3
    start_hour: int = 9
    end_hour: int = 22
    photo_count: int = 3


@router.post("/schedule-batch")
async def schedule_batch(
    payload: BatchScheduleIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Create N posting tasks per device, evenly spread across a time window."""
    from datetime import timedelta

    if not payload.device_ids:
        raise HTTPException(status_code=400, detail="device_ids required")
    if payload.days < 1 or payload.posts_per_day < 1:
        raise HTTPException(status_code=400, detail="days/posts_per_day must be >= 1")
    if payload.end_hour <= payload.start_hour:
        raise HTTPException(status_code=400, detail="end_hour must be > start_hour")

    now = datetime.utcnow()
    created: list[str] = []
    for device_id in payload.device_ids:
        for day in range(payload.days):
            base = (now + timedelta(days=day)).replace(
                hour=payload.start_hour, minute=0, second=0, microsecond=0
            )
            window_minutes = (payload.end_hour - payload.start_hour) * 60
            step = window_minutes // max(payload.posts_per_day, 1)
            for i in range(payload.posts_per_day):
                when = base + timedelta(minutes=step * i)
                if when <= now:
                    continue
                task = Task(
                    device_id=device_id,
                    account_id=payload.account_id,
                    task_type="post_publish",
                    status="pending",
                    priority=5,
                    scheduled_at=when,
                    payload={
                        "dataset_id": payload.dataset_id,
                        "platform": payload.platform,
                        "photo_count": payload.photo_count,
                    },
                )
                session.add(task)
                created.append(when.isoformat())
    await session.commit()
    return {"scheduled": len(created), "first": created[0] if created else None,
            "last": created[-1] if created else None}


@router.get("/queue")
async def queue_overview(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    stmt = (
        select(Task.device_id, Task.status, func.count())
        .where(Task.status.in_(("pending", "running")))
        .group_by(Task.device_id, Task.status)
    )
    rows = (await session.execute(stmt)).all()
    by_device: dict[str, dict[str, int]] = {}
    for device_id, status, count in rows:
        by_device.setdefault(device_id, {})[status] = count
    return {"by_device": by_device}


@router.get("/dlq", response_model=list[TaskRead])
async def dead_letter_queue(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(100, le=500),
) -> list[Task]:
    stmt = (
        select(Task)
        .where(Task.status == "dlq")
        .order_by(Task.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> Task:
    return await get_or_404(session, Task, task_id)


@router.put("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: str,
    payload: TaskUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Task:
    task = await get_or_404(session, Task, task_id)
    apply_update(task, payload)
    await session.commit()
    await session.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> Response:
    task = await get_or_404(session, Task, task_id)
    await session.delete(task)
    await session.commit()
    return Response(status_code=204)


@router.post("/{task_id}/retry", response_model=TaskRead)
async def retry_task(
    task_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> Task:
    task = await get_or_404(session, Task, task_id)
    if task.status not in {"failed", "dlq"}:
        raise HTTPException(409, f"Task in status '{task.status}' is not retriable")
    task.status = "pending"
    task.retry_count = (task.retry_count or 0) + 1
    task.error_message = None
    task.started_at = None
    task.completed_at = None
    await session.commit()
    await session.refresh(task)
    return task
