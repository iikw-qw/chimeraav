"""
API логов действий.
Зависит от: models/log, schemas/common, deps
"""

import csv
import io
from uuid import UUID
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.log import ActionLog
from app.models.user import User
from app.schemas.common import ActionLogResponse
from app.api.deps import get_current_user

router = APIRouter()


@router.get("", response_model=list[ActionLogResponse])
async def list_logs(
    action_type: Optional[str] = None,
    device_id: Optional[UUID] = None,
    account_id: Optional[UUID] = None,
    success: Optional[bool] = None,
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)
    query = select(ActionLog).where(ActionLog.created_at >= since)
    if action_type:
        query = query.where(ActionLog.action_type == action_type)
    if device_id:
        query = query.where(ActionLog.device_id == device_id)
    if account_id:
        query = query.where(ActionLog.account_id == account_id)
    if success is not None:
        query = query.where(ActionLog.success == success)
    query = query.order_by(ActionLog.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return [ActionLogResponse.model_validate(l) for l in result.scalars().all()]


@router.get("/export")
async def export_logs(
    days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(ActionLog)
        .where(ActionLog.created_at >= since)
        .order_by(ActionLog.created_at.desc())
        .limit(10000)
    )
    logs = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "device_id", "account_id", "action_type", "success", "duration_ms", "created_at", "details"])
    for log in logs:
        writer.writerow([
            log.id, str(log.device_id or ""), str(log.account_id or ""),
            log.action_type, log.success, log.duration_ms,
            log.created_at.isoformat() if log.created_at else "",
            str(log.details),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=chimera_logs.csv"},
    )
