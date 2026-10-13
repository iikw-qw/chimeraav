"""Active-stream registry — single-process in-memory state shared between
the producer-side WebSocket handler (/api/ws/stream/{device_id}) and
viewer-side handler (/api/ws/view/{device_id}).

Why in-memory and not Redis: the spec calls for Redis for SPS+PPS storage,
but this Chimera install runs as a single FastAPI process — there is no
Redis container. An in-memory dict is the correct adaptation; if/when the
deployment grows to multiple workers this can be swapped for aioredis with
no callers changing (the surface is async).

Хранит:
    SPS + PPS (parameter sets) каждого активного стрима — нужны новым
    зрителям, иначе их декодер не сможет начать с середины потока.
    Список подписанных зрителей (asyncio.Queue) — фреймы из producer-цикла
    кладутся в каждую очередь без блокировок продьюсера.
    Сводную статистику (fps/bitrate/resolution/viewers) — отдаётся через
    REST GET /api/streams/{device_id}.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class StreamStats:
    fps: float = 0.0
    bitrate_bps: int = 0
    resolution: str | None = None
    viewers: int = 0
    last_frame_at: float = 0.0
    keyframes: int = 0
    total_frames: int = 0
    total_bytes: int = 0


@dataclass
class ViewerQueue:
    """Per-viewer outbound queue. Bounded — if the viewer's network can't
    keep up we drop P-frames (mark `needs_keyframe=True`) and resume on the
    next I-frame to avoid memory blow-up."""

    queue: asyncio.Queue[bytes] = field(default_factory=lambda: asyncio.Queue(maxsize=240))
    needs_keyframe: bool = True  # new viewers must start at an I-frame
    dropped_frames: int = 0


@dataclass
class ActiveStream:
    device_id: str
    sps: bytes | None = None
    pps: bytes | None = None
    metadata: dict | None = None  # model, resolution, android_version, etc.
    started_at: float = field(default_factory=time.time)
    viewers: list[ViewerQueue] = field(default_factory=list)
    stats: StreamStats = field(default_factory=StreamStats)
    _frame_window: list[tuple[float, int]] = field(default_factory=list)  # (ts, bytes)

    def record_frame(self, frame: bytes, *, is_keyframe: bool) -> None:
        now = time.time()
        self.stats.last_frame_at = now
        self.stats.total_frames += 1
        self.stats.total_bytes += len(frame)
        if is_keyframe:
            self.stats.keyframes += 1
        # rolling 1-second window for fps/bitrate
        self._frame_window.append((now, len(frame)))
        cutoff = now - 1.0
        while self._frame_window and self._frame_window[0][0] < cutoff:
            self._frame_window.pop(0)
        if self._frame_window:
            duration = max(0.001, self._frame_window[-1][0] - self._frame_window[0][0])
            self.stats.fps = len(self._frame_window) / max(duration, 1e-3)
            self.stats.bitrate_bps = int(
                sum(b for _, b in self._frame_window) * 8 / max(duration, 1e-3)
            )


class StreamManager:
    def __init__(self) -> None:
        self._streams: dict[str, ActiveStream] = {}
        self._lock = asyncio.Lock()

    async def register_producer(self, device_id: str) -> ActiveStream:
        async with self._lock:
            existing = self._streams.get(device_id)
            if existing is not None:
                # producer reconnected — keep same viewers
                existing.started_at = time.time()
                return existing
            stream = ActiveStream(device_id=device_id)
            self._streams[device_id] = stream
            return stream

    async def unregister_producer(self, device_id: str) -> None:
        async with self._lock:
            stream = self._streams.pop(device_id, None)
        if stream is None:
            return
        # signal all viewers to disconnect
        for v in list(stream.viewers):
            try:
                v.queue.put_nowait(b"")  # empty bytes = sentinel
            except asyncio.QueueFull:
                pass

    def get(self, device_id: str) -> ActiveStream | None:
        return self._streams.get(device_id)

    async def add_viewer(self, device_id: str) -> tuple[ActiveStream, ViewerQueue] | None:
        stream = self._streams.get(device_id)
        if stream is None:
            return None
        viewer = ViewerQueue()
        stream.viewers.append(viewer)
        stream.stats.viewers = len(stream.viewers)
        return stream, viewer

    async def remove_viewer(self, device_id: str, viewer: ViewerQueue) -> None:
        stream = self._streams.get(device_id)
        if stream is None:
            return
        try:
            stream.viewers.remove(viewer)
        except ValueError:
            pass
        stream.stats.viewers = len(stream.viewers)

    def list_streams(self) -> list[ActiveStream]:
        return list(self._streams.values())


stream_manager = StreamManager()
