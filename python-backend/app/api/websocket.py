from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ._hub import CHANNELS, hub

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await hub.connect(ws)
    try:
        await ws.send_json({"type": "hello", "channels": sorted(CHANNELS)})
        while True:
            msg = await ws.receive_json()
            mtype = msg.get("type")
            channel = msg.get("channel")

            if mtype == "subscribe" and isinstance(channel, str):
                ok = await hub.subscribe(ws, channel)
                await ws.send_json(
                    {"type": "subscribed" if ok else "error", "channel": channel}
                )
            elif mtype == "unsubscribe" and isinstance(channel, str):
                await hub.unsubscribe(ws, channel)
                await ws.send_json({"type": "unsubscribed", "channel": channel})
            elif mtype == "ping":
                await ws.send_json({"type": "pong"})
            else:
                await ws.send_json({"type": "error", "message": "unknown message"})
    except WebSocketDisconnect:
        await hub.unsubscribe(ws)
    except Exception:
        await hub.unsubscribe(ws)
        try:
            await ws.close()
        except Exception:
            pass
