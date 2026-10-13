"""WebSocket pub/sub hub."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

CHANNELS = frozenset(
    {
        "devices",
        "tasks",
        "logs",
        "comments",
        "incoming_messages",
        "warmup",
        "welcome_progress",
        "cursor",
        "notifications",
        "auto_login",
        "ios_automation",
        "tunnel",
        "wda",
        "alert_watcher",
        "ocr",
        "cleanup",
        "telegram_notify",
    }
)


class Hub:
    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()

    async def subscribe(self, ws: WebSocket, channel: str) -> bool:
        if channel not in CHANNELS:
            return False
        async with self._lock:
            self._channels[channel].add(ws)
        return True

    async def unsubscribe(self, ws: WebSocket, channel: str | None = None) -> None:
        async with self._lock:
            if channel is not None:
                self._channels.get(channel, set()).discard(ws)
            else:
                for subs in self._channels.values():
                    subs.discard(ws)

    async def broadcast(self, channel: str, payload: Any) -> int:
        targets = list(self._channels.get(channel, ()))
        if not targets:
            return 0
        message = {"channel": channel, "data": payload}
        sent = 0
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
                sent += 1
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    for subs in self._channels.values():
                        subs.discard(ws)
        return sent

    def stats(self) -> dict[str, int]:
        return {channel: len(subs) for channel, subs in self._channels.items()}


hub = Hub()
