"""Centralised WebSocket connection manager with room-based broadcasting."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str) -> None:
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        self.rooms[room_id].add(websocket)
        logger.debug("WS connected to room %s (total=%d)", room_id, len(self.rooms[room_id]))

    async def disconnect(self, websocket: WebSocket, room_id: str) -> None:
        s = self.rooms.get(room_id)
        if s:
            s.discard(websocket)
            if not s:
                del self.rooms[room_id]

    async def broadcast(self, room_id: str, data: dict | bytes) -> None:
        sockets = list(self.rooms.get(room_id, []))
        for ws in sockets:
            try:
                if ws.client_state != WebSocketState.CONNECTED:
                    await self.disconnect(ws, room_id)
                    continue
                if isinstance(data, bytes):
                    await ws.send_bytes(data)
                else:
                    await ws.send_json(data)
            except Exception:
                await self.disconnect(ws, room_id)

    async def send_personal(self, websocket: WebSocket, data: dict) -> None:
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(data)
        except Exception:
            pass


ws_manager = ConnectionManager()
