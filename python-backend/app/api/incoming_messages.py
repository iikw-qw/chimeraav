from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incoming_message import IncomingMessage

from ._deps import get_or_404, get_session

router = APIRouter(prefix="/incoming-messages", tags=["incoming_messages"])


class IncomingMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    account_id: str
    sender_username: str | None = None
    sender_user_id: str | None = None
    message_text: str | None = None
    platform: str
    notified_to_telegram: bool
    notified_at: datetime | None = None
    received_at: datetime


@router.get("", response_model=list[IncomingMessageRead])
async def list_incoming(
    session: Annotated[AsyncSession, Depends(get_session)],
    account_id: str | None = None,
    platform: str | None = None,
    unread_only: bool = False,
    limit: int = Query(100, le=500),
    offset: int = 0,
) -> list[IncomingMessage]:
    stmt = select(IncomingMessage)
    if account_id:
        stmt = stmt.where(IncomingMessage.account_id == account_id)
    if platform:
        stmt = stmt.where(IncomingMessage.platform == platform)
    if unread_only:
        stmt = stmt.where(IncomingMessage.notified_to_telegram.is_(False))
    stmt = stmt.order_by(IncomingMessage.received_at.desc()).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/unread-count")
async def unread_count(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    count = (
        await session.scalar(
            select(func.count())
            .select_from(IncomingMessage)
            .where(IncomingMessage.notified_to_telegram.is_(False))
        )
        or 0
    )
    return {"unread": count}


class ReportPayload(BaseModel):
    account_id: str
    sender_username: str | None = None
    sender_user_id: str | None = None
    message_text: str
    platform: str


@router.post("/report", response_model=IncomingMessageRead, status_code=201)
async def report_message(
    payload: ReportPayload, session: Annotated[AsyncSession, Depends(get_session)]
) -> IncomingMessage:
    msg = IncomingMessage(**payload.model_dump())
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


@router.post("/{message_id}/mark-processed", response_model=IncomingMessageRead)
async def mark_processed(
    message_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> IncomingMessage:
    msg = await get_or_404(session, IncomingMessage, message_id)
    msg.notified_to_telegram = True
    msg.notified_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await session.commit()
    await session.refresh(msg)
    return msg
