from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.action_log import ActionLog
from app.models.comment import Comment
from app.models.device import Device
from app.models.incoming_message import IncomingMessage
from app.models.task import Task
from app.models.welcome_message import WelcomeMessage

from ._deps import get_session

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


_PLATFORMS = (
    "instagram",
    "tiktok",
    "telegram",
    "twitter",
    "facebook",
    "youtube",
    "reddit",
    "threads",
)


_BOOT_TS = datetime.now(timezone.utc)


async def _count_by(
    session: AsyncSession, model, column, values: tuple[str, ...]
) -> dict[str, int]:
    stmt = select(column, func.count()).group_by(column)
    rows = (await session.execute(stmt)).all()
    by_value = {str(v or ""): int(c) for v, c in rows}
    return {v: by_value.get(v, 0) for v in values}


@router.get("/metrics")
async def metrics(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    devices = await _count_by(
        session, Device, Device.status, ("online", "offline", "warming", "error")
    )
    accounts = await _count_by(
        session, Account, Account.status, ("active", "warming", "banned", "cooldown")
    )
    tasks_by_status = await _count_by(
        session, Task, Task.status, ("pending", "running", "completed", "failed")
    )

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    completed_today = (
        await session.execute(
            select(func.count())
            .select_from(Task)
            .where(Task.status == "completed", Task.completed_at >= today_start)
        )
    ).scalar_one()
    failed_today = (
        await session.execute(
            select(func.count())
            .select_from(Task)
            .where(Task.status == "failed", Task.completed_at >= today_start)
        )
    ).scalar_one()

    comments_today = (
        await session.execute(
            select(func.count())
            .select_from(Comment)
            .where(Comment.created_at >= today_start)
        )
    ).scalar_one()
    ready_for_welcome = (
        await session.execute(
            select(func.count())
            .select_from(Comment)
            .where(
                Comment.welcome_sent.is_(False),
                Comment.commenter_gender == "male",
            )
        )
    ).scalar_one()
    welcome_today = (
        await session.execute(
            select(func.count())
            .select_from(WelcomeMessage)
            .where(WelcomeMessage.sent_at >= today_start)
        )
    ).scalar_one()

    messages_today = (
        await session.execute(
            select(func.count())
            .select_from(IncomingMessage)
            .where(IncomingMessage.received_at >= today_start)
        )
    ).scalar_one()
    messages_unread = (
        await session.execute(
            select(func.count())
            .select_from(IncomingMessage)
            .where(IncomingMessage.notified_to_telegram.is_(False))
        )
    ).scalar_one()

    uptime = int((datetime.now(timezone.utc) - _BOOT_TS).total_seconds())

    return {
        "devices": devices,
        "accounts": accounts,
        "tasks": {
            "pending": tasks_by_status["pending"],
            "running": tasks_by_status["running"],
            "completed_today": int(completed_today),
            "failed_today": int(failed_today),
        },
        "comments": {
            "received_today": int(comments_today),
            "ready_for_welcome": int(ready_for_welcome),
            "welcome_sent_today": int(welcome_today),
        },
        "messages": {
            "unread": int(messages_unread),
            "received_today": int(messages_today),
        },
        "uptime_seconds": uptime,
        "version": "9.0.0",
    }


@router.get("/activity")
async def activity(
    session: Annotated[AsyncSession, Depends(get_session)],
    hours: int = 24,
) -> dict:
    hours = max(1, min(hours, 168))
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    window_start = now - timedelta(hours=hours)

    tasks_rows = (
        await session.execute(
            select(Task.completed_at, Task.status).where(
                Task.completed_at >= window_start,
                Task.status.in_(("completed", "failed")),
            )
        )
    ).all()
    comments_rows = (
        await session.execute(
            select(Comment.created_at).where(Comment.created_at >= window_start)
        )
    ).all()
    welcome_rows = (
        await session.execute(
            select(WelcomeMessage.sent_at).where(
                WelcomeMessage.sent_at >= window_start
            )
        )
    ).all()

    buckets: dict[str, dict[str, int]] = {}

    def _slot(ts: datetime) -> str:
        ts = ts.replace(minute=0, second=0, microsecond=0)
        return ts.isoformat()

    for h in range(hours, 0, -1):
        ts = now - timedelta(hours=h)
        buckets[ts.isoformat()] = {
            "tasks_completed": 0,
            "comments_received": 0,
            "welcome_sent": 0,
            "errors": 0,
        }

    for ts, status in tasks_rows:
        if ts is None:
            continue
        slot = _slot(ts)
        if slot not in buckets:
            continue
        if status == "completed":
            buckets[slot]["tasks_completed"] += 1
        elif status == "failed":
            buckets[slot]["errors"] += 1
    for (ts,) in comments_rows:
        slot = _slot(ts)
        if slot in buckets:
            buckets[slot]["comments_received"] += 1
    for (ts,) in welcome_rows:
        slot = _slot(ts)
        if slot in buckets:
            buckets[slot]["welcome_sent"] += 1

    points = [{"ts": ts, **vals} for ts, vals in buckets.items()]
    return {"window_hours": hours, "points": points}


@router.get("/platforms")
async def platforms(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict]:
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    accounts_rows = (
        await session.execute(
            select(Account.platform, func.count()).group_by(Account.platform)
        )
    ).all()
    accounts_by = {p: int(c) for p, c in accounts_rows}

    posts_rows = (
        await session.execute(
            select(Task.payload, func.count())
            .where(
                Task.task_type == "publish_post",
                Task.completed_at >= today_start,
                Task.status == "completed",
            )
            .group_by(Task.payload)
        )
    ).all()
    posts_by: dict[str, int] = {}
    for payload, count in posts_rows:
        platform = (payload or {}).get("platform") if isinstance(payload, dict) else None
        if platform:
            posts_by[platform] = posts_by.get(platform, 0) + int(count)

    comments_rows = (
        await session.execute(
            select(Comment.platform, func.count())
            .where(Comment.created_at >= today_start)
            .group_by(Comment.platform)
        )
    ).all()
    comments_by = {p: int(c) for p, c in comments_rows}

    welcome_rows = (
        await session.execute(
            select(Account.platform, func.count())
            .join(WelcomeMessage, WelcomeMessage.account_id == Account.id)
            .where(WelcomeMessage.sent_at >= today_start)
            .group_by(Account.platform)
        )
    ).all()
    welcome_by = {p: int(c) for p, c in welcome_rows}

    out: list[dict] = []
    for p in _PLATFORMS:
        acc = accounts_by.get(p, 0)
        health = "healthy" if acc > 0 else "idle"
        out.append(
            {
                "platform": p,
                "accounts": acc,
                "posts_today": posts_by.get(p, 0),
                "comments_today": comments_by.get(p, 0),
                "welcome_sent_today": welcome_by.get(p, 0),
                "health": health,
            }
        )
    return out


@router.get("/recent-tasks")
async def recent_tasks(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 10,
) -> list[dict]:
    limit = max(1, min(limit, 100))
    stmt = (
        select(Task)
        .order_by(Task.completed_at.desc().nullslast(), Task.created_at.desc())
        .limit(limit)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    out: list[dict] = []
    for t in rows:
        duration_ms = None
        if t.started_at and t.completed_at:
            duration_ms = int((t.completed_at - t.started_at).total_seconds() * 1000)
        platform = None
        if isinstance(t.payload, dict):
            platform = t.payload.get("platform")
        out.append(
            {
                "id": t.id,
                "type": t.task_type,
                "platform": platform,
                "status": t.status,
                "duration_ms": duration_ms,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
        )
    return out


@router.get("/recent-errors")
async def recent_errors(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 10,
) -> list[dict]:
    limit = max(1, min(limit, 100))
    stmt = (
        select(ActionLog)
        .where(ActionLog.level.in_(("error", "warning")))
        .order_by(ActionLog.created_at.desc())
        .limit(limit)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    out: list[dict] = []
    for r in rows:
        details = r.details if isinstance(r.details, dict) else {}
        out.append(
            {
                "id": r.id,
                "code": str(details.get("code") or r.action_type),
                "message": str(details.get("message") or ""),
                "level": r.level,
                "occurred_at": r.created_at.isoformat(),
            }
        )
    return out
