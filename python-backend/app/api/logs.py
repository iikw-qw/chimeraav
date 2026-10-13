"""Logs API — query and stream action logs."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._deps import get_session
from app.models.action_log import ActionLog

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("")
async def get_logs(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    level: str | None = None,
    device_id: str | None = None,
    action_type: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    stmt = select(ActionLog)

    if level:
        stmt = stmt.where(ActionLog.level == level)
    if device_id:
        stmt = stmt.where(ActionLog.device_id == device_id)
    if action_type:
        stmt = stmt.where(ActionLog.action_type == action_type)

    stmt = stmt.order_by(desc(ActionLog.created_at)).offset(offset).limit(limit)

    rows = (await session.execute(stmt)).scalars().all()

    result = []
    for row in reversed(rows):
        entry = {
            "id": row.id,
            "created_at": row.created_at.isoformat() if row.created_at else "",
            "level": row.level,
            "device_id": row.device_id,
            "action_type": row.action_type,
            "details": row.details,
        }
        if search:
            haystack = f"{row.action_type} {row.details}".lower()
            if search.lower() not in haystack:
                continue
        result.append(entry)

    return result


@router.get("/stats")
async def get_log_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    total = await session.scalar(select(func.count()).select_from(ActionLog)) or 0

    by_level = {}
    for lvl in ("info", "warning", "error", "debug"):
        count = await session.scalar(
            select(func.count()).select_from(ActionLog).where(ActionLog.level == lvl)
        ) or 0
        by_level[lvl] = count

    return {"total": total, "by_level": by_level}


@router.get("/action-types")
async def get_action_types(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[str]:
    stmt = select(ActionLog.action_type).distinct().order_by(ActionLog.action_type)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


@router.delete("/clear")
async def clear_logs(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    from sqlalchemy import delete
    result = await session.execute(delete(ActionLog))
    await session.commit()
    return {"ok": True, "deleted": result.rowcount or 0}
