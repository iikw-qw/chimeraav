"""
Менеджер стримов: трекинг, ретрансляция, метрики.
"""

import asyncio
from typing import Dict, Set
from fastapi import WebSocket


class StreamManager:
    def __init__(self):
        self._streams: Dict[str, Set[WebSocket]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def register_stream(self, device_id: str):
        self._streams[device_id] = set()
        self._locks[device_id] = asyncio.Lock()

    def unregister_stream(self, device_id: str):
        self._streams.pop(device_id, None)
        self._locks.pop(device_id, None)

    def is_streaming(self, device_id: str) -> bool:
        return device_id in self._streams

    async def add_viewer(self, device_id: str, websocket: WebSocket):
        if device_id in self._streams:
            self._streams[device_id].add(websocket)

    async def remove_viewer(self, device_id: str, websocket: WebSocket):
        if device_id in self._streams:
            self._streams[device_id].discard(websocket)

    def get_viewer_count(self, device_id: str) -> int:
        return len(self._streams.get(device_id, set()))

    async def broadcast_frame(self, device_id: str, data: bytes):
        viewers = self._streams.get(device_id, set()).copy()
        if not viewers:
            return

        disconnected = []
        for viewer in viewers:
            try:
                await viewer.send_bytes(data)
            except Exception:
                disconnected.append(viewer)

        for viewer in disconnected:
            self._streams.get(device_id, set()).discard(viewer)

    def get_all_streams(self) -> Dict[str, int]:
        return {did: len(viewers) for did, viewers in self._streams.items()}


stream_manager = StreamManager()
