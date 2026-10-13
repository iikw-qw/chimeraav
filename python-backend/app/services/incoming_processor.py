"""Process incoming DMs — persist, notify Telegram, optionally auto-reply."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.api._hub import hub
from app.database import SessionLocal
from app.models.account import Account
from app.models.app_settings import AppSettings
from app.models.incoming_message import IncomingMessage
from app.services.auto_chatter import auto_chatter
from app.services.telegram_notifier import TelegramNotifier

_TELEGRAM_KEY = "telegram"


class IncomingMessageProcessor:
    """Pipeline for inbound DMs: save → Telegram notify → optional auto-reply → WS."""

    async def process(self, event: dict[str, Any]) -> dict[str, Any]:
        account_id = event["account_id"]

        async with SessionLocal() as session:
            account = await session.get(Account, account_id)
            if account is None:
                raise ValueError(f"Account {account_id} not found")

            if not account.notify_new_messages:
                return {"saved": False, "reason": "notifications_disabled"}

            message = IncomingMessage(
                account_id=account_id,
                sender_username=event.get("sender_username") or event.get("sender"),
                sender_user_id=event.get("sender_user_id"),
                message_text=event.get("message_text") or event.get("text"),
                platform=event.get("platform", account.platform),
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)

            telegram_cfg = await self._load_telegram_cfg(session)
            auto_reply_enabled = account.auto_reply_enabled

        notify_stats = await self._notify_telegram(message, telegram_cfg)

        if notify_stats.get("sent", 0) > 0:
            async with SessionLocal() as session:
                fresh = await session.get(IncomingMessage, message.id)
                if fresh is not None:
                    fresh.notified_to_telegram = True
                    fresh.notified_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()

        reply_result: dict[str, Any] | None = None
        if auto_reply_enabled:
            sender = message.sender_username or message.sender_user_id or "user"
            text = message.message_text or ""
            try:
                reply_result = await auto_chatter.handle_reply(
                    account_id, sender, text
                )
            except Exception as exc:  # pragma: no cover - network
                reply_result = {"error": str(exc)}

        payload = {
            "id": message.id,
            "account_id": message.account_id,
            "sender_username": message.sender_username,
            "sender_user_id": message.sender_user_id,
            "message_text": message.message_text,
            "platform": message.platform,
            "received_at": message.received_at.isoformat()
            if message.received_at
            else None,
            "auto_reply": reply_result,
        }
        await hub.broadcast("incoming_messages", payload)

        return {
            "saved": True,
            "message_id": message.id,
            "telegram": notify_stats,
            "auto_reply": reply_result,
        }

    @staticmethod
    async def _load_telegram_cfg(session) -> dict[str, Any]:
        row = (
            await session.execute(
                select(AppSettings).where(AppSettings.key == _TELEGRAM_KEY)
            )
        ).scalar_one_or_none()
        if row is None or not isinstance(row.value, dict):
            return {}
        return row.value

    async def _notify_telegram(
        self, message: IncomingMessage, cfg: dict[str, Any]
    ) -> dict[str, int]:
        if not cfg.get("enabled") or not cfg.get("notify_new_messages", True):
            return {"sent": 0, "failed": 0, "skipped": True}
        token = cfg.get("bot_token")
        chat_id = cfg.get("chat_id")
        if not token or not chat_id:
            return {"sent": 0, "failed": 0, "skipped": True}

        chat_ids = [chat_id] if isinstance(chat_id, str) else list(chat_id)
        notifier = TelegramNotifier(token, chat_ids)
        return await notifier.notify_new_message(message)


incoming_processor = IncomingMessageProcessor()
