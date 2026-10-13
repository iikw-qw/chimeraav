"""
WebSocket: broadcast изменений глобальных настроек всем клиентам.
Зависит от: redis_client
"""

import asyncio
import json
import structlog
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = structlog.get_logger()
router = APIRouter()

connected_clients: Set[WebSocket] = set()


@router.websocket("/ws/settings")
async def settings_websocket(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info("settings_ws.connected", total=len(connected_clients))

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(websocket)
        logger.info("settings_ws.disconnected", total=len(connected_clients))


async def broadcast_setting_change(key: str, value):
    message = json.dumps({"type": "setting_changed", "key": key, "value": value})
    disconnected = []
    for client in connected_clients.copy():
        try:
            await client.send_text(message)
        except Exception:
            disconnected.append(client)
    for client in disconnected:
        connected_clients.discard(client)
