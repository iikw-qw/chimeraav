"""Per-device asyncio.PriorityQueue."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass(order=True)
class _Task:
    priority: int
    seq: int
    payload: Any = field(compare=False)


class DeviceTaskQueue:
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.PriorityQueue[_Task]] = {}
        self._lock = asyncio.Lock()
        self._seq = 0

    async def _queue_for(self, device_id: str) -> asyncio.PriorityQueue[_Task]:
        async with self._lock:
            q = self._queues.get(device_id)
            if q is None:
                q = asyncio.PriorityQueue()
                self._queues[device_id] = q
            return q

    async def put(self, device_id: str, payload: Any, priority: int = 5) -> None:
        q = await self._queue_for(device_id)
        async with self._lock:
            self._seq += 1
            seq = self._seq
        await q.put(_Task(priority=priority, seq=seq, payload=payload))

    async def get(self, device_id: str) -> Any:
        q = await self._queue_for(device_id)
        task = await q.get()
        return task.payload

    def task_done(self, device_id: str) -> None:
        q = self._queues.get(device_id)
        if q is not None:
            q.task_done()

    def size(self, device_id: str) -> int:
        q = self._queues.get(device_id)
        return q.qsize() if q else 0

    def devices(self) -> list[str]:
        return list(self._queues.keys())


task_queue = DeviceTaskQueue()
