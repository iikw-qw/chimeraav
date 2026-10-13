"""
WebSocket: приём H.264-стрима от Android/iOS агентов.
Сохраняет SPS+PPS в Redis, ретранслирует всем зрителям (zero-copy).
Зависит от: redis_client, stream_manager
"""

import json
import time
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.redis_client import redis_client
from app.ws.stream_manager import stream_manager

logger = structlog.get_logger()
router = APIRouter()


@router.websocket("/ws/stream/{device_id}")
async def stream_websocket(websocket: WebSocket, device_id: str):
    await websocket.accept()
    logger.info("stream.connected", device_id=device_id)

    first_message = True
    frame_count = 0
    start_time = time.time()

    try:
        metadata = await websocket.receive_text()
        meta = json.loads(metadata)
        await redis_client.hset("chimera:active_streams", device_id, {
            "device_id": device_id,
            "model": meta.get("model", "unknown"),
            "resolution": meta.get("resolution", "unknown"),
            "os_version": meta.get("os_version", "unknown"),
            "battery": meta.get("battery", 0),
            "ip_address": meta.get("ip_address", ""),
            "external_ip": meta.get("external_ip", ""),
            "vpn_active": meta.get("vpn_active", False),
            "connected_at": time.time(),
            "viewers": 0,
        })

        stream_manager.register_stream(device_id)

        while True:
            data = await websocket.receive_bytes()
            frame_count += 1

            if first_message:
                await redis_client.set_stream_sps_pps(device_id, data)
                first_message = False

            await stream_manager.broadcast_frame(device_id, data)

            if frame_count % 300 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed if elapsed > 0 else 0
                await redis_client.hset("chimera:active_streams", device_id, {
                    "fps": round(fps, 1),
                    "frames": frame_count,
                    "viewers": stream_manager.get_viewer_count(device_id),
                })

    except WebSocketDisconnect:
        logger.info("stream.disconnected", device_id=device_id)
    except Exception as e:
        logger.error("stream.error", device_id=device_id, error=str(e))
    finally:
        stream_manager.unregister_stream(device_id)
        await redis_client.hdel("chimera:active_streams", device_id)
