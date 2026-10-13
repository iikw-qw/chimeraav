"""
ADB-прокси: выполнение ADB-команд из Docker-контейнера.
Пробует локальный adb, затем через host.docker.internal.
"""

import asyncio
import subprocess
from typing import Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)


def adb_shell_sync(serial: str, cmd: str, timeout: int = 15) -> str:
    """Синхронное выполнение ADB shell команды."""
    try:
        r = subprocess.run(
            ["adb", "-s", serial, "shell", cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.stdout.strip()
    except FileNotFoundError:
        try:
            r = subprocess.run(
                ["adb", "-H", "host.docker.internal", "-s", serial, "shell", cmd],
                capture_output=True, text=True, timeout=timeout,
            )
            return r.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""
    except subprocess.TimeoutExpired:
        return ""


async def adb_shell(serial: str, cmd: str, timeout: int = 15) -> str:
    """Асинхронное выполнение ADB shell команды."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "adb", "-s", serial, "shell", cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return stdout.decode("utf-8", errors="replace").strip()
    except FileNotFoundError:
        try:
            proc = await asyncio.create_subprocess_exec(
                "adb", "-H", "host.docker.internal", "-s", serial, "shell", cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return stdout.decode("utf-8", errors="replace").strip()
        except (FileNotFoundError, asyncio.TimeoutError):
            return ""
    except asyncio.TimeoutError:
        return ""


async def adb_devices() -> list[str]:
    """Получить список подключённых устройств."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "adb", "devices",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        lines = stdout.decode().strip().splitlines()[1:]
        return [l.split("\t")[0] for l in lines if "\tdevice" in l]
    except (FileNotFoundError, asyncio.TimeoutError):
        try:
            proc = await asyncio.create_subprocess_exec(
                "adb", "-H", "host.docker.internal", "devices",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            lines = stdout.decode().strip().splitlines()[1:]
            return [l.split("\t")[0] for l in lines if "\tdevice" in l]
        except (FileNotFoundError, asyncio.TimeoutError):
            return []


async def adb_push(serial: str, local_path: str, remote_path: str, timeout: int = 30) -> bool:
    """Push файла на устройство."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "adb", "-s", serial, "push", local_path, remote_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode == 0
    except (FileNotFoundError, asyncio.TimeoutError):
        return False


async def adb_screencap(serial: str) -> Optional[bytes]:
    """Скриншот устройства."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "adb", "-s", serial, "exec-out", "screencap", "-p",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        if proc.returncode == 0 and stdout:
            return stdout
    except (FileNotFoundError, asyncio.TimeoutError):
        pass
    return None
