"""Welcome message dispatcher — picks ready comments, queues tasks, persists log."""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._hub import hub
from app.database import SessionLocal
from app.models.comment import Comment
from app.models.message_template import MessageTemplate
from app.models.task import Task
from app.models.welcome_message import WelcomeMessage
from app.rate_limiter import rate_limiter

Selection = Literal["first", "random", "newest"]


class WelcomeService:
    """Pick quality male commenters that haven't received a welcome yet."""

    async def get_ready_for_welcome(
        self, account_id: str, limit: int = 200
    ) -> list[Comment]:
        async with SessionLocal() as session:
            return await self._ready_query(session, account_id, limit)

    async def send_welcome_bulk(
        self,
        account_id: str,
        *,
        comment_ids: list[str] | None = None,
        count: int | None = None,
        selection: Selection = "first",
        delay_between: float = 30.0,
    ) -> dict[str, int]:
        async with SessionLocal() as session:
            if comment_ids:
                stmt = (
                    select(Comment)
                    .where(
                        Comment.id.in_(comment_ids),
                        Comment.account_id == account_id,
                        Comment.welcome_sent.is_(False),
                    )
                )
                targets = list((await session.execute(stmt)).scalars().all())
            else:
                pool = await self._ready_query(session, account_id, limit=1000)
                targets = self._pick(pool, count or 0, selection)

            templates = await self._load_templates(session)

        total = len(targets)
        sent = 0
        failed = 0

        await hub.broadcast(
            "welcome_progress",
            {"account_id": account_id, "total": total, "sent": 0, "failed": 0},
        )

        for idx, comment in enumerate(targets):
            try:
                await rate_limiter.acquire(account_id)
                template = random.choice(templates) if templates else None
                text = template.template_text if template else "Hi! Nice to meet you!"
                await self._dispatch_welcome(account_id, comment, text)
                sent += 1
            except Exception:
                failed += 1

            await hub.broadcast(
                "welcome_progress",
                {
                    "account_id": account_id,
                    "total": total,
                    "sent": sent,
                    "failed": failed,
                },
            )

            if delay_between > 0 and idx < total - 1:
                await asyncio.sleep(delay_between)

        return {"total": total, "sent": sent, "failed": failed}

    async def _ready_query(
        self, session: AsyncSession, account_id: str, limit: int
    ) -> list[Comment]:
        stmt = (
            select(Comment)
            .where(
                Comment.account_id == account_id,
                Comment.welcome_sent.is_(False),
                Comment.commenter_gender == "male",
            )
            .order_by(Comment.created_at.desc())
            .limit(limit)
        )
        rows = list((await session.execute(stmt)).scalars().all())
        return [c for c in rows if self._is_quality(c)]

    @staticmethod
    def _is_quality(comment: Comment) -> bool:
        analysis = comment.commenter_profile_analysis or {}
        return analysis.get("quality") == "quality"

    @staticmethod
    async def _load_templates(session: AsyncSession) -> list[MessageTemplate]:
        stmt = select(MessageTemplate).where(
            MessageTemplate.is_active.is_(True),
            MessageTemplate.language == "en",
        )
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    def _pick(
        pool: list[Comment], count: int, selection: Selection
    ) -> list[Comment]:
        if count <= 0 or not pool:
            return []
        if selection == "first":
            return pool[:count]
        if selection == "newest":
            return sorted(pool, key=lambda c: c.created_at, reverse=True)[:count]
        if selection == "random":
            return random.sample(pool, min(count, len(pool)))
        return pool[:count]

    async def _dispatch_welcome(
        self, account_id: str, comment: Comment, text: str
    ) -> None:
        async with SessionLocal() as session:
            fresh = await session.get(Comment, comment.id)
            if fresh is None or fresh.welcome_sent:
                return

            device_id = await self._device_for_account(session, account_id)

            task = Task(
                device_id=device_id,
                account_id=account_id,
                task_type="send_welcome_dm",
                priority=5,
                payload={
                    "comment_id": fresh.id,
                    "recipient_username": fresh.commenter_username,
                    "message_text": text,
                    "language": "en",
                },
            )
            session.add(task)

            fresh.welcome_sent = True
            fresh.welcome_sent_at = datetime.now(timezone.utc).replace(tzinfo=None)

            session.add(
                WelcomeMessage(
                    account_id=account_id,
                    comment_id=fresh.id,
                    message_text=text,
                    language="en",
                    status="sent",
                )
            )
            await session.commit()

    @staticmethod
    async def _device_for_account(session: AsyncSession, account_id: str) -> str:
        from app.models.account import Account

        account = await session.get(Account, account_id)
        if account is None:
            raise ValueError(f"Account {account_id} not found")
        return account.device_id


welcome_service = WelcomeService()
