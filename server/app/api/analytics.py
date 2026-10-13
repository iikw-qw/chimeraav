"""
API аналитики.
Зависит от: models, deps
"""

from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.task import Task
from app.models.post import Post
from app.models.log import ActionLog
from app.models.account import SocialAccount
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/overview")
async def analytics_overview(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)

    posts_count = await db.execute(
        select(func.count(Post.id)).where(
            Post.user_id == current_user.id,
            Post.created_at >= since,
        )
    )
    tasks_completed = await db.execute(
        select(func.count(Task.id)).where(
            Task.user_id == current_user.id,
            Task.status == "completed",
            Task.completed_at >= since,
        )
    )
    tasks_failed = await db.execute(
        select(func.count(Task.id)).where(
            Task.user_id == current_user.id,
            Task.status == "failed",
            Task.completed_at >= since,
        )
    )

    return {
        "period_days": days,
        "posts": posts_count.scalar(),
        "tasks_completed": tasks_completed.scalar(),
        "tasks_failed": tasks_failed.scalar(),
    }


@router.get("/posts-by-day")
async def posts_by_day(
    days: int = Query(30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(
            cast(Post.created_at, Date).label("date"),
            func.count(Post.id).label("count"),
        )
        .where(Post.user_id == current_user.id, Post.created_at >= since)
        .group_by(cast(Post.created_at, Date))
        .order_by(cast(Post.created_at, Date))
    )
    return [{"date": str(row.date), "count": row.count} for row in result.all()]


@router.get("/accounts-comparison")
async def accounts_comparison(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SocialAccount).where(SocialAccount.user_id == current_user.id)
    )
    accounts = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "username": a.username,
            "platform": a.platform,
            "followers": a.followers_count,
            "following": a.following_count,
            "posts": a.posts_count,
        }
        for a in accounts
    ]


@router.get("/activity-heatmap")
async def activity_heatmap(
    days: int = Query(30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(
            func.extract("dow", Task.created_at).label("day_of_week"),
            func.extract("hour", Task.created_at).label("hour"),
            func.count(Task.id).label("count"),
        )
        .where(Task.user_id == current_user.id, Task.created_at >= since)
        .group_by("day_of_week", "hour")
    )
    return [
        {"day": int(row.day_of_week), "hour": int(row.hour), "count": row.count}
        for row in result.all()
    ]
