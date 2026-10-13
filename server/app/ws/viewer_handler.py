"""
WebSocket: отдача H.264-стрима зрителям.
При подключении — SPS+PPS из Redis, затем live-поток.
Зависит от: redis_client, stream_manager
"""

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.redis_client import redis_client
from app.ws.stream_manager import stream_manager

logger = structlog.get_logger()
router = APIRouter()


@router.websocket("/ws/view/{device_id}")
async def viewer_websocket(websocket: WebSocket, device_id: str):
    await websocket.accept()
    logger.info("viewer.connected", device_id=device_id)

    if not stream_manager.is_streaming(device_id):
        await websocket.send_json({"error": "Stream not available"})
        await websocket.close()
        return

    sps_pps = await redis_client.get_stream_sps_pps(device_id)
    if sps_pps:
        try:
            await websocket.send_bytes(sps_pps)
        except Exception:
            return

    await stream_manager.add_viewer(device_id, websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("viewer.disconnected", device_id=device_id)
    except Exception as e:
        logger.error("viewer.error", device_id=device_id, error=str(e))
    finally:
        await stream_manager.remove_viewer(device_id, websocket)
