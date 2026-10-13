"""Device heartbeat — ping all known devices every 5 seconds."""
from __future__ import annotations

import asyncio
import logging
import time

from utils.adb_utils import adb_cmd, adb_devices, is_adb_available
from utils.ws_manager import ws_manager

logger = logging.getLogger(__name__)

_device_status: dict[str, dict] = {}

HEARTBEAT_INTERVAL = 5
MAX_MISSED_HEARTBEATS = 3


async def heartbeat_loop() -> None:
    """Background task: ping all known devices every 5 seconds."""
    while True:
        try:
            if not is_adb_available():
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                continue
            devs = adb_devices()
            connected = {d["serial"] for d in devs if d["state"] == "device"}

            for serial in connected:
                start = time.time()
                try:
                    ping = adb_cmd(serial, ["shell", "echo", "ping"], timeout=3)
                    latency = int((time.time() - start) * 1000)

                    if "ping" in ping.stdout:
                        _device_status[serial] = {
                            "last_heartbeat": time.time(),
                            "online": True,
                            "latency_ms": latency,
                            "consecutive_fails": 0,
                        }
                    else:
                        _increment_fail(serial)
                except Exception:
                    _increment_fail(serial)

            for serial in list(_device_status.keys()):
                if serial not in connected:
                    if _device_status[serial].get("online"):
                        _device_status[serial]["online"] = False
                        await ws_manager.broadcast("devices", {
                            "event": "device_offline",
                            "serial": serial,
                        })
                        logger.warning("Device offline: %s", serial)

        except Exception as exc:
            logger.error("Heartbeat loop error: %s", exc)

        await asyncio.sleep(HEARTBEAT_INTERVAL)


def _increment_fail(serial: str) -> None:
    if serial not in _device_status:
        _device_status[serial] = {
            "last_heartbeat": 0, "online": False,
            "latency_ms": 0, "consecutive_fails": 0,
        }
    _device_status[serial]["consecutive_fails"] += 1
    if _device_status[serial]["consecutive_fails"] >= MAX_MISSED_HEARTBEATS:
        _device_status[serial]["online"] = False


def is_device_online(serial: str) -> bool:
    return _device_status.get(serial, {}).get("online", False)


def get_device_latency(serial: str) -> int:
    return _device_status.get(serial, {}).get("latency_ms", 0)


def get_all_device_status() -> dict:
    return dict(_device_status)
