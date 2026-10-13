"""H.264 live-streaming API.

Three concrete surfaces:

  - WS  /api/ws/stream/{device_id}  — Android agent uploads NAL units here
  - WS  /api/ws/view/{device_id}    — Browser viewer receives NAL units here
  - REST /api/streams                — list active streams
  - REST /api/streams/{device_id}    — single stream status
  - POST /api/streams/{device_id}/screenshot — capture one JPEG via existing
                                              ADB pipeline (works even if
                                              no H.264 stream is active —
                                              shared with /api/devices/.../screenshot).

The producer (Android) protocol:
  1. First text/JSON message:    {device_id, model, resolution, android_version, battery_level}
  2. Subsequent binary messages: one NAL unit per message, Annex-B prefixed.
  3. Optional text/JSON every 10s: {fps, bitrate, ...} — used for telemetry only.

Viewer protocol (browser):
  1. Binary stream of NAL units. SPS+PPS first, then I-frame, then live.
  2. JSON ping/pong allowed (for keep-alive); no other text traffic expected.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.services.stream_manager import stream_manager
from app.services.stream_relay import handle_producer_frame, prime_new_viewer

from ._deps import get_or_404, get_session

logger = logging.getLogger("chimera.streaming")

router = APIRouter(tags=["streaming"])


# ─── REST ──────────────────────────────────────────────────────────────────

class StreamSummary(BaseModel):
    device_id: str
    fps: float
    bitrate_bps: int
    resolution: str | None
    viewers: int
    has_keyframe: bool
    started_at: float
    metadata: dict | None = None


@router.get("/streams", response_model=list[StreamSummary])
async def list_streams() -> list[StreamSummary]:
    return [
        StreamSummary(
            device_id=s.device_id,
            fps=round(s.stats.fps, 2),
            bitrate_bps=s.stats.bitrate_bps,
            resolution=s.stats.resolution,
            viewers=s.stats.viewers,
            has_keyframe=s.stats.keyframes > 0,
            started_at=s.started_at,
            metadata=s.metadata,
        )
        for s in stream_manager.list_streams()
    ]


@router.get("/streams/{device_id}", response_model=StreamSummary)
async def get_stream(device_id: str) -> StreamSummary:
    s = stream_manager.get(device_id)
    if s is None:
        raise HTTPException(404, "stream not active")
    return StreamSummary(
        device_id=s.device_id,
        fps=round(s.stats.fps, 2),
        bitrate_bps=s.stats.bitrate_bps,
        resolution=s.stats.resolution,
        viewers=s.stats.viewers,
        has_keyframe=s.stats.keyframes > 0,
        started_at=s.started_at,
        metadata=s.metadata,
    )


@router.post("/streams/{device_id}/screenshot")
async def screenshot(
    device_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> Response:
    """One-shot JPEG. Reuses the existing ADB screencap pipeline so this works
    whether or not the H.264 stream is currently active."""
    from app.api.devices import _capture_android, _capture_ios, _PLACEHOLDER_PNG

    device = await get_or_404(session, Device, device_id)
    serial = device.serial or device.id
    img = None
    if device.platform == "android":
        img = await _capture_android(serial)
    elif device.platform == "ios":
        img = await _capture_ios(serial)
    if img is None:
        return Response(content=_PLACEHOLDER_PNG, media_type="image/png")
    return Response(content=img, media_type="image/png",
                    headers={"Cache-Control": "no-store"})


# ─── WS: producer (Android agent → server) ────────────────────────────────

@router.websocket("/ws/stream/{device_id}")
async def ws_stream_producer(ws: WebSocket, device_id: str) -> None:
    await ws.accept()
    stream = await stream_manager.register_producer(device_id)
    logger.info("stream producer connected: %s", device_id)
    try:
        while True:
            msg = await ws.receive()
            if "bytes" in msg and msg["bytes"] is not None:
                await handle_producer_frame(stream, msg["bytes"])
            elif "text" in msg and msg["text"] is not None:
                # control/metadata channel: parse JSON
                try:
                    data = json.loads(msg["text"])
                except json.JSONDecodeError:
                    continue
                kind = data.get("type")
                if kind == "metadata":
                    stream.metadata = {
                        k: data.get(k)
                        for k in ("model", "resolution", "android_version",
                                  "battery_level", "device_id")
                        if data.get(k) is not None
                    }
                    if data.get("resolution"):
                        stream.stats.resolution = data["resolution"]
                elif kind == "stats":
                    # Agent's own self-report — informational, server's
                    # measured stats stay authoritative.
                    pass
                elif kind == "heartbeat":
                    await ws.send_text(json.dumps({"type": "heartbeat_ack",
                                                    "ts": time.time()}))
            elif msg.get("type") == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("stream producer error %s: %s", device_id, exc)
    finally:
        await stream_manager.unregister_producer(device_id)
        logger.info("stream producer disconnected: %s", device_id)


# ─── WS: viewer (browser ← server) ────────────────────────────────────────

@router.websocket("/ws/view/{device_id}")
async def ws_stream_viewer(ws: WebSocket, device_id: str) -> None:
    await ws.accept()
    pair = await stream_manager.add_viewer(device_id)
    if pair is None:
        await ws.send_text(json.dumps({"type": "error", "code": "stream_offline"}))
        await ws.close(code=4404)
        return
    stream, viewer = pair
    logger.info("viewer connected to %s (total=%d)", device_id, len(stream.viewers))
    await prime_new_viewer(stream, viewer)

    async def _pump() -> None:
        while True:
            frame = await viewer.queue.get()
            if frame == b"":  # producer-disconnect sentinel
                break
            try:
                await ws.send_bytes(frame)
            except Exception:
                break

    pump_task = asyncio.create_task(_pump())
    try:
        # Drain inbound (ping/pong only) until the socket dies or the pump
        # signals shutdown.
        while True:
            done, _ = await asyncio.wait(
                {pump_task, asyncio.create_task(ws.receive_text())},
                return_when=asyncio.FIRST_COMPLETED,
                timeout=None,
            )
            if pump_task in done:
                break
            for d in done:
                try:
                    txt = d.result()
                except Exception:
                    return
                try:
                    msg = json.loads(txt)
                except Exception:
                    continue
                if msg.get("type") == "ping":
                    await ws.send_text(json.dumps({"type": "pong", "ts": time.time()}))
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("viewer error %s: %s", device_id, exc)
    finally:
        if not pump_task.done():
            pump_task.cancel()
        await stream_manager.remove_viewer(device_id, viewer)
        try:
            await ws.close()
        except Exception:
            pass
        logger.info("viewer disconnected from %s", device_id)
