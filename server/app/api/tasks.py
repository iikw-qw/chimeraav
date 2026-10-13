"""
API управления задачами.
Зависит от: models/task, schemas/task, deps, redis_client
"""

from uuid import UUID
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from app.api.deps import get_current_user
from app.services.redis_client import redis_client

router = APIRouter()


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    task_type: Optional[str] = None,
    status: Optional[str] = None,
    device_id: Optional[UUID] = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Task).where(Task.user_id == current_user.id)
    if task_type:
        query = query.where(Task.task_type == task_type)
    if status:
        query = query.where(Task.status == status)
    if device_id:
        query = query.where(Task.device_id == device_id)
    query = query.order_by(Task.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return [TaskResponse.model_validate(t) for t in result.scalars().all()]


@router.get("/stats")
async def task_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stats = {}
    for s in ["pending", "queued", "running", "completed", "failed", "retrying", "dead"]:
        result = await db.execute(
            select(func.count(Task.id)).where(Task.user_id == current_user.id, Task.status == s)
        )
        stats[s] = result.scalar()
    return stats


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    data: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = Task(user_id=current_user.id, **data.model_dump())
    db.add(task)
    await db.flush()
    await db.refresh(task)

    await redis_client.add_task("chimera:tasks", {
        "task_id": str(task.id),
        "task_type": task.task_type,
        "device_id": str(task.device_id) if task.device_id else None,
        "account_id": str(task.account_id) if task.account_id else None,
        "payload": task.payload,
    })

    return TaskResponse.model_validate(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    data: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)

    if data.status == "running" and not task.started_at:
        task.started_at = datetime.utcnow()
    elif data.status in ("completed", "failed", "dead"):
        task.completed_at = datetime.utcnow()

    await db.flush()
    await db.refresh(task)
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}")
async def delete_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    return {"message": "Task deleted"}
