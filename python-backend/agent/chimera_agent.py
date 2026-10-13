"""Chimera Agent — scrcpy-based agent auto-install with WebSocket progress."""
from __future__ import annotations

import asyncio
import logging
import os

from utils.adb_utils import adb_cmd, adb_devices, find_adb, is_adb_available
from utils.ws_manager import ws_manager

logger = logging.getLogger(__name__)

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRCPY_PATH = os.path.join(AGENT_DIR, "scrcpy-server.jar")
SCRCPY_SERVER_URL = "https://github.com/Genymobile/scrcpy/releases/download/v2.4/scrcpy-server-v2.4"


async def download_scrcpy_if_missing() -> bool:
    if os.path.exists(SCRCPY_PATH):
        return True
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(SCRCPY_SERVER_URL, follow_redirects=True, timeout=60)
            with open(SCRCPY_PATH, "wb") as f:
                f.write(resp.content)
        logger.info("scrcpy-server downloaded")
        return True
    except Exception as e:
        logger.error("Failed to download scrcpy-server: %s", e)
        return False


async def install_agent(serial: str) -> dict:
    room = f"agent_install_{serial}"

    try:
        await ws_manager.broadcast(room, {"step": 1, "message": "Checking ADB connection...", "percent": 10})

        if not is_adb_available():
            return {"status": "error", "serial": serial, "message": "ADB not found. Install Android Platform Tools."}

        devs = adb_devices()
        device_serials = [d["serial"] for d in devs if d["state"] == "device"]
        if serial not in device_serials:
            return {
                "status": "error",
                "serial": serial,
                "message": "Device not found. Enable USB Debugging in Developer Options, "
                           "connect USB cable, and tap 'Allow' on the phone.",
            }

        await ws_manager.broadcast(room, {"step": 2, "message": "Preparing agent...", "percent": 30})
        await download_scrcpy_if_missing()

        await ws_manager.broadcast(room, {"step": 3, "message": "Installing on device...", "percent": 50})

        if os.path.exists(SCRCPY_PATH):
            adb_cmd(serial, ["push", SCRCPY_PATH, "/data/local/tmp/scrcpy-server.jar"], timeout=30)

        await ws_manager.broadcast(room, {"step": 4, "message": "Verifying installation...", "percent": 80})

        check = adb_cmd(serial, ["shell", "ls", "/data/local/tmp/scrcpy-server.jar"], timeout=5)

        if "No such file" in check.stdout or check.returncode != 0:
            return {"status": "error", "serial": serial, "message": "Agent installation failed"}

        model = adb_cmd(serial, ["shell", "getprop", "ro.product.model"], timeout=5).stdout.strip()

        android_ver = adb_cmd(serial, ["shell", "getprop", "ro.build.version.release"], timeout=5).stdout.strip()

        await ws_manager.broadcast(room, {
            "step": 5,
            "message": f"Agent ready! {model} (Android {android_ver})",
            "percent": 100,
            "status": "ok",
        })

        return {
            "status": "ok",
            "serial": serial,
            "model": model,
            "android_version": android_ver,
            "message": f"Agent installed on {model}",
        }

    except Exception as e:
        logger.error("Agent install failed for %s: %s", serial, e)
        return {"status": "error", "serial": serial, "message": str(e)}


async def get_agent_status(serial: str) -> dict:
    if not is_adb_available():
        return {"serial": serial, "installed": False, "adb_available": False}
    try:
        check = adb_cmd(serial, ["shell", "ls", "/data/local/tmp/scrcpy-server.jar"], timeout=5)
        installed = "No such file" not in check.stdout and check.returncode == 0
        return {"serial": serial, "installed": installed, "adb_available": True}
    except Exception:
        return {"serial": serial, "installed": False}


AGENT_PACKAGE = "com.chimera.agent"
AGENT_APK_PATH = os.path.join(AGENT_DIR, "chimera-agent.apk")


async def check_agent_version(serial: str) -> dict:
    """Compare installed agent version with bundled version."""
    import re as _re
    installed_ver = ""
    try:
        result = adb_cmd(serial, ["shell", "dumpsys", "package", AGENT_PACKAGE], timeout=10)
        m = _re.search(r"versionName=(\S+)", result.stdout)
        if m:
            installed_ver = m.group(1)
    except Exception:
        pass

    bundled_ver = "1.0.0"
    needs_update = installed_ver != bundled_ver and installed_ver != ""

    return {
        "installed": installed_ver,
        "bundled": bundled_ver,
        "needs_update": needs_update,
    }


async def update_agent_if_needed(serial: str) -> bool:
    """Auto-update agent if newer version bundled."""
    info = await check_agent_version(serial)
    if info["needs_update"] and os.path.exists(AGENT_APK_PATH):
        adb_cmd(serial, ["install", "-r", "-g", AGENT_APK_PATH], timeout=60)
        logger.info("Agent updated on %s: %s → %s", serial, info["installed"], info["bundled"])
        return True
    return False
