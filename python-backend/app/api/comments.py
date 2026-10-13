from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment
from app.models.welcome_message import WelcomeMessage

from ._deps import get_or_404, get_session

router = APIRouter(prefix="/comments", tags=["comments"])


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    account_id: str
    platform: str
    post_id_external: str | None = None
    commenter_username: str | None = None
    commenter_user_id: str | None = None
    commenter_gender: str
    commenter_language: str | None = None
    comment_text: str | None = None
    reply_text: str | None = None
    reply_status: str
    welcome_sent: bool
    created_at: datetime


def _filter(stmt, **filters):
    for col, val in filters.items():
        if val is not None:
            stmt = stmt.where(getattr(Comment, col) == val)
    return stmt


@router.get("", response_model=list[CommentRead])
async def list_comments(
    session: Annotated[AsyncSession, Depends(get_session)],
    platform: str | None = None,
    gender: Annotated[str | None, Query(alias="gender")] = None,
    language: str | None = None,
    reply_status: str | None = None,
    welcome_sent: bool | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
) -> list[Comment]:
    stmt = select(Comment)
    stmt = _filter(
        stmt,
        platform=platform,
        commenter_gender=gender,
        commenter_language=language,
        reply_status=reply_status,
        welcome_sent=welcome_sent,
    )
    stmt = stmt.order_by(Comment.created_at.desc()).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/ready-for-welcome", response_model=list[CommentRead])
async def ready_for_welcome(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(200, le=1000),
) -> list[Comment]:
    stmt = (
        select(Comment)
        .where(
            Comment.welcome_sent.is_(False),
            Comment.commenter_gender == "male",
        )
        .order_by(Comment.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.get("/stats")
async def comments_stats(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    total = await session.scalar(select(func.count()).select_from(Comment)) or 0
    by_gender_stmt = select(Comment.commenter_gender, func.count()).group_by(
        Comment.commenter_gender
    )
    by_gender = {row[0]: row[1] for row in (await session.execute(by_gender_stmt)).all()}
    by_status_stmt = select(Comment.reply_status, func.count()).group_by(Comment.reply_status)
    by_status = {row[0]: row[1] for row in (await session.execute(by_status_stmt)).all()}
    welcome_done = (
        await session.scalar(
            select(func.count()).select_from(Comment).where(Comment.welcome_sent.is_(True))
        )
        or 0
    )
    return {
        "total": total,
        "by_gender": by_gender,
        "by_reply_status": by_status,
        "welcome_sent": welcome_done,
    }


@router.get("/export")
async def export_comments(
    session: Annotated[AsyncSession, Depends(get_session)],
    platform: str | None = None,
    gender: str | None = None,
) -> StreamingResponse:
    stmt = select(Comment)
    stmt = _filter(stmt, platform=platform, commenter_gender=gender)
    stmt = stmt.order_by(Comment.created_at.desc())
    rows = list((await session.execute(stmt)).scalars().all())

    async def stream() -> AsyncIterator[bytes]:
        wb = Workbook(write_only=True)
        ws = wb.create_sheet("comments")
        headers = [
            "id",
            "account_id",
            "platform",
            "post_id_external",
            "username",
            "gender",
            "language",
            "comment_text",
            "reply_status",
            "welcome_sent",
            "created_at",
        ]
        ws.append(headers)
        for c in rows:
            ws.append(
                [
                    c.id,
                    c.account_id,
                    c.platform,
                    c.post_id_external,
                    c.commenter_username,
                    c.commenter_gender,
                    c.commenter_language,
                    c.comment_text,
                    c.reply_status,
                    c.welcome_sent,
                    c.created_at.isoformat() if c.created_at else None,
                ]
            )
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        chunk_size = 64 * 1024
        while True:
            chunk = buf.read(chunk_size)
            if not chunk:
                break
            yield chunk

    filename = f"comments-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.xlsx"
    return StreamingResponse(
        stream(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{comment_id}/send-welcome", response_model=CommentRead)
async def send_welcome_one(
    comment_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> Comment:
    comment = await get_or_404(session, Comment, comment_id)
    if comment.welcome_sent:
        return comment
    comment.welcome_sent = True
    comment.welcome_sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(
        WelcomeMessage(
            account_id=comment.account_id,
            comment_id=comment.id,
            message_text="Hi! Nice to meet you!",
            language=comment.commenter_language or "en",
            status="sent",
        )
    )
    await session.commit()
    await session.refresh(comment)
    return comment


class BulkWelcomePayload(BaseModel):
    comment_ids: list[str]


@router.post("/bulk-welcome")
async def bulk_welcome(
    payload: BulkWelcomePayload,
    background: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    if not payload.comment_ids:
        return {"queued": 0}
    background.add_task(_bulk_welcome_job, payload.comment_ids)
    return {"queued": len(payload.comment_ids), "status": "scheduled"}


async def _bulk_welcome_job(comment_ids: list[str]) -> None:
    from app.database import SessionLocal

    async with SessionLocal() as session:
        stmt = select(Comment).where(Comment.id.in_(comment_ids))
        rows = list((await session.execute(stmt)).scalars().all())
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for c in rows:
            if c.welcome_sent:
                continue
            c.welcome_sent = True
            c.welcome_sent_at = now
            session.add(
                WelcomeMessage(
                    account_id=c.account_id,
                    comment_id=c.id,
                    message_text="Hi! Nice to meet you!",
                    language=c.commenter_language or "en",
                    status="sent",
                )
            )
        await session.commit()
