"""APK Deployer — auto-install Chimera agent on Android devices via ADB."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("chimera.apk_deployer")

APK_PACKAGE = "com.chimera.agent"
APK_ACTIVITY = f"{APK_PACKAGE}/.MainActivity"

REQUIRED_PERMISSIONS = [
    "android.permission.SYSTEM_ALERT_WINDOW",
    "android.permission.WRITE_EXTERNAL_STORAGE",
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.CAMERA",
    "android.permission.RECORD_AUDIO",
    "android.permission.FOREGROUND_SERVICE",
    "android.permission.ACCESS_FINE_LOCATION",
]


class APKDeployer:
    def __init__(self, apk_path: str | None = None) -> None:
        self._apk_path = apk_path or self._find_apk()

    def _find_apk(self) -> str:
        candidates = [
            Path("agent-android/chimera-agent.apk"),
            Path("chimera-agent.apk"),
            Path("resources/chimera-agent.apk"),
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        return "chimera-agent.apk"

    async def _run_adb(self, *args: str, timeout: float = 30) -> tuple[str, str, int]:
        proc = await asyncio.create_subprocess_exec(
            "adb", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return "", "timeout", -1
        return (
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
            proc.returncode or 0,
        )

    async def list_connected_devices(self) -> list[dict[str, str]]:
        stdout, _, rc = await self._run_adb("devices", "-l")
        if rc != 0:
            return []
        devices = []
        for line in stdout.strip().split("\n")[1:]:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] == "device":
                serial = parts[0]
                model = ""
                for p in parts[2:]:
                    if p.startswith("model:"):
                        model = p.split(":")[1]
                devices.append({"serial": serial, "model": model})
        return devices

    async def is_agent_installed(self, serial: str) -> bool:
        stdout, _, rc = await self._run_adb("-s", serial, "shell", "pm", "list", "packages")
        if rc != 0:
            return False
        return APK_PACKAGE in stdout

    async def get_agent_version(self, serial: str) -> str | None:
        stdout, _, rc = await self._run_adb(
            "-s", serial, "shell", "dumpsys", "package", APK_PACKAGE
        )
        if rc != 0:
            return None
        for line in stdout.split("\n"):
            if "versionName" in line:
                return line.strip().split("=")[-1]
        return None

    async def install_agent(self, serial: str, upgrade: bool = False) -> dict[str, Any]:
        apk = Path(self._apk_path)
        if not apk.exists():
            return {"ok": False, "error": f"APK not found: {self._apk_path}"}

        flag = "-r" if upgrade else ""
        args = ["-s", serial, "install"]
        if flag:
            args.append(flag)
        args.append(str(apk))

        stdout, stderr, rc = await self._run_adb(*args, timeout=120)
        if rc != 0 or "Failure" in stdout + stderr:
            return {"ok": False, "error": (stdout + stderr).strip()}

        logger.info("Agent installed on %s", serial)
        return {"ok": True, "serial": serial, "action": "upgrade" if upgrade else "install"}

    async def grant_permissions(self, serial: str) -> list[str]:
        granted = []
        for perm in REQUIRED_PERMISSIONS:
            _, _, rc = await self._run_adb("-s", serial, "shell", "pm", "grant", APK_PACKAGE, perm)
            if rc == 0:
                granted.append(perm)
        return granted

    async def launch_agent(self, serial: str) -> bool:
        _, _, rc = await self._run_adb(
            "-s", serial, "shell", "am", "start", "-n", APK_ACTIVITY
        )
        return rc == 0

    async def deploy_to_device(self, serial: str) -> dict[str, Any]:
        """Full deployment: check → install → permissions → launch."""
        installed = await self.is_agent_installed(serial)

        if installed:
            result = await self.install_agent(serial, upgrade=True)
        else:
            result = await self.install_agent(serial, upgrade=False)

        if not result.get("ok"):
            return result

        granted = await self.grant_permissions(serial)
        launched = await self.launch_agent(serial)

        return {
            "ok": True,
            "serial": serial,
            "action": "upgrade" if installed else "install",
            "permissions_granted": len(granted),
            "launched": launched,
        }

    async def auto_deploy_new_devices(self, known_serials: set[str] | None = None) -> list[dict]:
        """Scan for new devices and auto-deploy the agent."""
        known = known_serials or set()
        devices = await self.list_connected_devices()
        results = []
        for dev in devices:
            serial = dev["serial"]
            if serial in known:
                continue
            if not await self.is_agent_installed(serial):
                result = await self.deploy_to_device(serial)
                result["model"] = dev.get("model", "")
                results.append(result)
        return results


apk_deployer = APKDeployer()
