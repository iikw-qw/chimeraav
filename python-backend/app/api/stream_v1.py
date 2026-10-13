"""Stream v1 router — screen streaming, screenshots, agent install."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from agent.stream_agent import stream_agent
from utils.ws_manager import ws_manager

router = APIRouter(prefix="/v1/stream", tags=["stream-v1"])


@router.post("/start/{serial}")
async def v1_start_stream(serial: str):
    ok = stream_agent.start(serial)
    return {"ok": ok, "serial": serial}


@router.post("/stop/{serial}")
async def v1_stop_stream(serial: str):
    stream_agent.stop(serial)
    return {"ok": True}


@router.get("/active")
async def v1_active_streams():
    return {"streams": stream_agent.list_active()}


@router.get("/screenshot/{serial}")
async def v1_screenshot(serial: str):
    data = stream_agent.screenshot(serial)
    if data:
        return Response(content=data, media_type="image/png")
    return {"error": "Screenshot failed"}


@router.post("/start-all")
async def v1_start_all_streams():
    from utils.adb_utils import adb_devices
    devs = adb_devices()
    serials = [d["serial"] for d in devs if d["state"] == "device"]
    results = [{"serial": s, "streaming": stream_agent.start(s)} for s in serials]
    return {"total": len(serials), "results": results}


# WebSocket for live H.264 frames
ws_router = APIRouter()


@ws_router.websocket("/api/ws/stream/{serial}")
async def ws_stream(websocket: WebSocket, serial: str):
    room = f"stream_{serial}"
    await ws_manager.connect(websocket, room)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, room)
