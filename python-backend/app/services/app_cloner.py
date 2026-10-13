"""Clone social apps via Android multi-user profiles."""

from __future__ import annotations

import asyncio
import logging
import re

logger = logging.getLogger("chimera.app_cloner")


async def _run(cmd: list[str], timeout: float = 15.0) -> tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return 127, f"{cmd[0]} not found"
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "timeout"
    return proc.returncode or 0, stdout.decode("utf-8", errors="replace")


class AppCloner:
    def __init__(self, serial: str, adb: str = "adb"):
        self.serial = serial
        self.adb = adb

    async def create_clone(self, package: str, clone_index: int = 1) -> dict:
        code, out = await _run(
            [self.adb, "-s", self.serial, "shell",
             "pm", "create-user", f"chimera_clone_{clone_index}"],
        )
        if "Success" in out:
            user_match = re.search(r"user (\d+)", out, re.IGNORECASE)
            if user_match:
                uid = user_match.group(1)
                await _run(
                    [self.adb, "-s", self.serial, "shell",
                     "pm", "install-existing", "--user", uid, package],
                )
                await _run(
                    [self.adb, "-s", self.serial, "shell",
                     "am", "start", "--user", uid,
                     "-n", f"{package}/.MainActivity"],
                )
                return {"success": True, "user_id": uid, "method": "multi_user"}

        return {"success": False, "error": "Клонирование недоступно на этом устройстве"}

    async def list_clones(self) -> list[dict]:
        code, out = await _run(
            [self.adb, "-s", self.serial, "shell", "pm", "list", "users"],
        )
        users = re.findall(r"UserInfo\{(\d+):([^:]+):", out)
        return [
            {"id": u[0], "name": u[1]}
            for u in users
            if "chimera" in u[1].lower()
        ]

    async def remove_clone(self, user_id: str) -> dict:
        code, out = await _run(
            [self.adb, "-s", self.serial, "shell",
             "pm", "remove-user", user_id],
        )
        return {"success": "Success" in out, "output": out.strip()}
