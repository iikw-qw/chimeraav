"""
API планировщика.
Зависит от: models/scheduler_plan, schemas/common, deps
"""

from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.scheduler_plan import SchedulerPlan
from app.models.user import User
from app.schemas.common import SchedulerPlanCreate, SchedulerPlanUpdate, SchedulerPlanResponse
from app.api.deps import get_current_user

router = APIRouter()


@router.get("", response_model=list[SchedulerPlanResponse])
async def list_plans(
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(SchedulerPlan).where(SchedulerPlan.user_id == current_user.id)
    if status:
        query = query.where(SchedulerPlan.status == status)
    query = query.order_by(SchedulerPlan.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return [SchedulerPlanResponse.model_validate(p) for p in result.scalars().all()]


@router.post("", response_model=SchedulerPlanResponse, status_code=201)
async def create_plan(
    data: SchedulerPlanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = SchedulerPlan(user_id=current_user.id, **data.model_dump())
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return SchedulerPlanResponse.model_validate(plan)


@router.get("/{plan_id}", response_model=SchedulerPlanResponse)
async def get_plan(
    plan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SchedulerPlan).where(SchedulerPlan.id == plan_id, SchedulerPlan.user_id == current_user.id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return SchedulerPlanResponse.model_validate(plan)


@router.put("/{plan_id}", response_model=SchedulerPlanResponse)
async def update_plan(
    plan_id: UUID,
    data: SchedulerPlanUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SchedulerPlan).where(SchedulerPlan.id == plan_id, SchedulerPlan.user_id == current_user.id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)

    await db.flush()
    await db.refresh(plan)
    return SchedulerPlanResponse.model_validate(plan)


@router.delete("/{plan_id}")
async def delete_plan(
    plan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SchedulerPlan).where(SchedulerPlan.id == plan_id, SchedulerPlan.user_id == current_user.id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    await db.delete(plan)
    return {"message": "Plan deleted"}
