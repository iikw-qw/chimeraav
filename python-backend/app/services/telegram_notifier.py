"""Telegram notifier — push DM notifications to one or more chat IDs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import httpx

from app.database import SessionLocal
from app.models.account import Account
from app.models.device import Device
from app.models.incoming_message import IncomingMessage
from app.models.proxy import Proxy

_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_ids: Iterable[str | int]) -> None:
        self._token = bot_token
        self._chat_ids = [str(x) for x in chat_ids]

    async def notify_new_message(self, incoming: IncomingMessage) -> dict[str, int]:
        if not self._token or not self._chat_ids:
            return {"sent": 0, "failed": 0}

        text = await self._render(incoming)
        sent = 0
        failed = 0

        url = _API_URL.format(token=self._token)
        async with httpx.AsyncClient(timeout=15.0) as client:
            for chat_id in self._chat_ids:
                try:
                    response = await client.post(
                        url,
                        json={
                            "chat_id": chat_id,
                            "text": text,
                            "parse_mode": "Markdown",
                            "disable_web_page_preview": True,
                        },
                    )
                    response.raise_for_status()
                    sent += 1
                except Exception:
                    failed += 1

        return {"sent": sent, "failed": failed}

    async def _render(self, incoming: IncomingMessage) -> str:
        async with SessionLocal() as session:
            account = await session.get(Account, incoming.account_id)
            device = (
                await session.get(Device, account.device_id) if account else None
            )
            proxy = (
                await session.get(Proxy, device.proxy_id)
                if device and device.proxy_id
                else None
            )

        phone = device.phone_number if device else "—"
        username = account.username if account else "—"
        platform = incoming.platform
        country = proxy.country if proxy and proxy.country else "—"
        sender = incoming.sender_username or incoming.sender_user_id or "unknown"
        raw = (incoming.message_text or "").strip()
        snippet = raw[:150] + ("…" if len(raw) > 150 else "")
        ts = incoming.received_at or datetime.now(timezone.utc)
        time_str = ts.strftime("%Y-%m-%d %H:%M")

        return (
            "📨 *Новое сообщение*\n"
            f"📱 *Устройство:* `{phone}`\n"
            f"👤 *Аккаунт:* @{username} ({platform})\n"
            f"🌐 *VPN/Proxy:* {country}\n"
            f"*От:* @{sender}\n"
            f"_{snippet}_\n"
            f"🕐 _{time_str}_"
        )
