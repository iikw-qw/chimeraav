"""Centralized ADB command execution with auto-discovery, retry, and timeout."""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys

from utils.logger import get_logger

logger = get_logger(__name__)

_adb_lock = asyncio.Lock()
_adb_path: str | None = None

_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def find_adb() -> str:
    global _adb_path
    if _adb_path and os.path.exists(_adb_path):
        return _adb_path

    found = shutil.which("adb")
    if found:
        _adb_path = found
        logger.info("ADB found in PATH: %s", found)
        return found

    search_paths = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Chimera", "tools", "platform-tools", "adb.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk", "platform-tools", "adb.exe"),
        os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "Android", "Sdk", "platform-tools", "adb.exe"),
        r"C:\platform-tools\adb.exe",
        r"C:\adb\adb.exe",
        r"C:\Android\platform-tools\adb.exe",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "adb.exe"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "adb", "adb.exe"),
    ]

    for p in search_paths:
        if p and os.path.isfile(p):
            _adb_path = p
            logger.info("ADB found at: %s", p)
            return p

    logger.warning("ADB not found — device features will be unavailable")
    return "adb"


def is_adb_available() -> bool:
    adb = find_adb()
    try:
        r = subprocess.run(
            [adb, "version"], capture_output=True, timeout=5,
            creationflags=_CREATE_NO_WINDOW,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def adb_devices() -> list[dict]:
    try:
        result = subprocess.run(
            [find_adb(), "devices"], capture_output=True, text=True, timeout=5,
            creationflags=_CREATE_NO_WINDOW,
        )
        devices = []
        for line in result.stdout.strip().split("\n")[1:]:
            parts = line.strip().split("\t")
            if len(parts) == 2:
                devices.append({"serial": parts[0], "state": parts[1]})
        return devices
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []


def adb_cmd(serial: str | None, args: list[str],
            timeout: int = 15) -> subprocess.CompletedProcess:
    adb = find_adb()
    cmd = [adb]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
    except FileNotFoundError:
        logger.error("ADB not found at '%s'", adb)
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="ADB not found")
    except subprocess.TimeoutExpired:
        logger.warning("ADB timeout (%ds): %s", timeout, " ".join(cmd))
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="Timeout")


async def adb_restart():
    adb = find_adb()
    async with _adb_lock:
        subprocess.run([adb, "kill-server"], capture_output=True, timeout=5,
                       creationflags=_CREATE_NO_WINDOW)
        await asyncio.sleep(1)
        subprocess.run([adb, "start-server"], capture_output=True, timeout=5,
                       creationflags=_CREATE_NO_WINDOW)
        await asyncio.sleep(2)
        logger.info("ADB server restarted")


async def adb_command(
    serial: str,
    cmd: list[str],
    timeout: int = 10,
    retries: int = 2,
) -> subprocess.CompletedProcess:
    adb = find_adb()
    full_cmd = [adb, "-s", serial] + cmd
    result = None

    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                full_cmd, capture_output=True, text=True, timeout=timeout,
                creationflags=_CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                return result

            if "device not found" in result.stderr.lower():
                if attempt < retries:
                    logger.warning("Device %s not found, restarting ADB...", serial)
                    await adb_restart()
                    await asyncio.sleep(1)
                    continue

            if "device offline" in result.stderr.lower():
                if attempt < retries:
                    logger.warning("Device %s offline, waiting...", serial)
                    await asyncio.sleep(3)
                    continue

            return result

        except FileNotFoundError:
            logger.error("ADB not found at '%s'", adb)
            return subprocess.CompletedProcess(full_cmd, returncode=1, stdout="", stderr="ADB not found")
        except subprocess.TimeoutExpired:
            logger.warning("ADB timeout for %s: %s (attempt %d)", serial, cmd, attempt + 1)
            if attempt < retries:
                await asyncio.sleep(2)
                continue
            return subprocess.CompletedProcess(full_cmd, returncode=1, stdout="", stderr="Timeout")

    return result  # type: ignore[return-value]


async def adb_shell(serial: str, shell_cmd: str, timeout: int = 10) -> str:
    result = await adb_command(serial, ["shell"] + shell_cmd.split(), timeout)
    return result.stdout.strip()


async def adb_input(serial: str, input_cmd: str):
    await adb_command(serial, ["shell", "input"] + input_cmd.split(), timeout=5)


async def get_connected_serials() -> list[str]:
    devs = adb_devices()
    return [d["serial"] for d in devs if d["state"] == "device"]
