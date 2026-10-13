"""Unified pool of male users — commenters + DM senders — for welcome-bulk."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.comment import Comment
from app.models.incoming_message import IncomingMessage

from ._deps import get_session

router = APIRouter(prefix="/users-pool", tags=["users_pool"])


try:
    import gender_guesser.detector as _gg_module  # type: ignore

    _DETECTOR = _gg_module.Detector(case_sensitive=False)
except Exception:  # pragma: no cover
    _DETECTOR = None


_MALE_TOKENS = {"male", "mostly_male"}


def _looks_male(username: str | None) -> bool:
    """Best-effort male-gender inference from a social handle.

    Extracts the first alpha-only token from the handle, strips digits,
    and runs gender_guesser. Returns False for unknowns to stay safe
    (we only want confident males).
    """
    if not username:
        return False
    if _DETECTOR is None:
        return False
    clean = "".join(ch if ch.isalpha() else " " for ch in username).strip()
    if not clean:
        return False
    first = clean.split()[0]
    if len(first) < 2:
        return False
    return _DETECTOR.get_gender(first.capitalize()) in _MALE_TOKENS


class PoolUser(BaseModel):
    key: str                  # stable id: "comment:{id}" or "dm:{id}"
    source: str               # "comment" | "dm"
    account_id: str
    platform: str
    username: str | None
    user_id: str | None
    preview: str | None       # comment text or last message
    created_at: datetime
    welcome_sent: bool


@router.get("", response_model=list[PoolUser])
async def list_users_pool(
    session: Annotated[AsyncSession, Depends(get_session)],
    account_id: str | None = None,
    platform: str | None = None,
    source: str | None = Query(None, pattern="^(comment|dm)$"),
    limit: int = Query(500, le=2000),
) -> list[PoolUser]:
    out: list[PoolUser] = []

    if source in (None, "comment"):
        c_stmt = select(Comment).where(
            Comment.commenter_gender == "male",
        )
        if account_id:
            c_stmt = c_stmt.where(Comment.account_id == account_id)
        if platform:
            c_stmt = c_stmt.where(Comment.platform == platform)
        c_stmt = c_stmt.order_by(Comment.created_at.desc()).limit(limit)
        for c in (await session.execute(c_stmt)).scalars().all():
            out.append(
                PoolUser(
                    key=f"comment:{c.id}",
                    source="comment",
                    account_id=c.account_id,
                    platform=c.platform,
                    username=c.commenter_username,
                    user_id=c.commenter_user_id,
                    preview=c.comment_text,
                    created_at=c.created_at,
                    welcome_sent=bool(c.welcome_sent),
                )
            )

    if source in (None, "dm"):
        m_stmt = select(IncomingMessage)
        if account_id:
            m_stmt = m_stmt.where(IncomingMessage.account_id == account_id)
        if platform:
            m_stmt = m_stmt.where(IncomingMessage.platform == platform)
        m_stmt = m_stmt.order_by(IncomingMessage.received_at.desc()).limit(limit)
        for m in (await session.execute(m_stmt)).scalars().all():
            if not _looks_male(m.sender_username):
                continue
            out.append(
                PoolUser(
                    key=f"dm:{m.id}",
                    source="dm",
                    account_id=m.account_id,
                    platform=m.platform,
                    username=m.sender_username,
                    user_id=m.sender_user_id,
                    preview=m.message_text,
                    created_at=m.received_at,
                    welcome_sent=False,
                )
            )

    out.sort(key=lambda u: u.created_at, reverse=True)
    return out[:limit]


class BulkSendPayload(BaseModel):
    keys: list[str]               # ["comment:<id>", "dm:<id>", ...]
    count: int | None = None      # if keys empty, pick N from pool
    selection: str = "first"      # first | random | newest
    account_id: str | None = None
    message_text: str | None = None
    delay_seconds: float = 30.0


@router.post("/bulk-welcome")
async def bulk_welcome(
    payload: BulkSendPayload,
    background: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    if not payload.keys and (payload.count or 0) <= 0:
        raise HTTPException(400, "keys or count must be provided")

    background.add_task(_bulk_job, payload.model_dump())
    queued = len(payload.keys) if payload.keys else int(payload.count or 0)
    return {"queued": queued, "status": "scheduled"}


async def _bulk_job(payload: dict) -> None:
    import asyncio
    import random

    from app.api._hub import hub
    from app.database import SessionLocal
    from app.models.task import Task
    from app.models.welcome_message import WelcomeMessage
    from app.rate_limiter import rate_limiter

    keys: list[str] = list(payload.get("keys") or [])
    text = (payload.get("message_text") or "Hi! Nice to meet you!").strip()
    delay = float(payload.get("delay_seconds") or 30.0)
    account_id = payload.get("account_id")

    if not keys:
        # pull from pool by count/selection
        async with SessionLocal() as session:
            pool = await list_users_pool(
                session=session,
                account_id=account_id,
                platform=None,
                source=None,
                limit=1000,
            )
        pool = [p for p in pool if not p.welcome_sent]
        selection = payload.get("selection") or "first"
        count = int(payload.get("count") or 0)
        if selection == "random":
            random.shuffle(pool)
        elif selection == "newest":
            pool.sort(key=lambda p: p.created_at, reverse=True)
        keys = [p.key for p in pool[:count]]

    total = len(keys)
    sent = 0
    failed = 0
    await hub.broadcast(
        "welcome_progress",
        {"account_id": account_id or "", "total": total, "sent": 0, "failed": 0},
    )

    for idx, key in enumerate(keys):
        try:
            kind, ident = key.split(":", 1)
        except ValueError:
            failed += 1
            continue

        try:
            async with SessionLocal() as session:
                if kind == "comment":
                    c = await session.get(Comment, ident)
                    if c is None or c.welcome_sent:
                        continue
                    acct = await session.get(Account, c.account_id)
                    if acct is None or not acct.device_id:
                        failed += 1
                        continue
                    await rate_limiter.acquire(c.account_id)
                    task = Task(
                        device_id=acct.device_id,
                        account_id=c.account_id,
                        task_type="send_welcome_dm",
                        priority=5,
                        payload={
                            "comment_id": c.id,
                            "recipient_username": c.commenter_username,
                            "message_text": text,
                            "language": "en",
                        },
                    )
                    session.add(task)
                    c.welcome_sent = True
                    c.welcome_sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    session.add(
                        WelcomeMessage(
                            account_id=c.account_id,
                            comment_id=c.id,
                            message_text=text,
                            language="en",
                            status="sent",
                        )
                    )
                    await session.commit()
                    sent += 1
                elif kind == "dm":
                    m = await session.get(IncomingMessage, ident)
                    if m is None:
                        continue
                    acct = await session.get(Account, m.account_id)
                    if acct is None or not acct.device_id:
                        failed += 1
                        continue
                    await rate_limiter.acquire(m.account_id)
                    task = Task(
                        device_id=acct.device_id,
                        account_id=m.account_id,
                        task_type="send_welcome_dm",
                        priority=5,
                        payload={
                            "recipient_username": m.sender_username,
                            "message_text": text,
                            "language": "en",
                        },
                    )
                    session.add(task)
                    session.add(
                        WelcomeMessage(
                            account_id=m.account_id,
                            comment_id=None,
                            message_text=text,
                            language="en",
                            status="sent",
                        )
                    )
                    await session.commit()
                    sent += 1
        except Exception:
            failed += 1

        await hub.broadcast(
            "welcome_progress",
            {
                "account_id": account_id or "",
                "total": total,
                "sent": sent,
                "failed": failed,
            },
        )

        if delay > 0 and idx < total - 1:
            await asyncio.sleep(delay)
