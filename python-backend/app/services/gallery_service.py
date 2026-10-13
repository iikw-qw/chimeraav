"""Gallery service — push media to the phone's DCIM and notify media scanner.

All posting (photo + video) must originate from the device gallery so that
Instagram/TikTok see a native pick flow, not an adb-shell-injected asset.

Flow per post:
 1. For each local file, push to /sdcard/DCIM/Camera/chimera_<timestamp>_<n>.<ext>
 2. Broadcast MEDIA_SCANNER_SCAN_FILE so the system indexes the new file
 3. Return device-side paths so the posting step can pick them from gallery
 4. After the post is published, optionally delete the pushed files to keep
    the gallery clean (the Instagram upload already stored its own copy).
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from app.database import SessionLocal
from app.models.device import Device
from app.services import tools as tools_svc

DEVICE_GALLERY_DIR = "/sdcard/DCIM/Camera"
PUSHED_PREFIX = "chimera_"


async def _run(cmd: list[str], timeout: float = 30.0) -> tuple[int, str]:
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
    return proc.returncode or 0, (stdout + stderr).decode("utf-8", errors="replace")


class GalleryService:
    async def _serial(self, device_id: str) -> str:
        async with SessionLocal() as session:
            device = await session.get(Device, device_id)
            if device is None:
                raise ValueError(f"Device {device_id} not found")
            if device.platform != "android":
                raise ValueError("gallery service is Android-only")
            return device.serial or device.id

    def _adb(self) -> str:
        adb = tools_svc.resolve("adb")
        if adb is None:
            raise RuntimeError("adb unavailable")
        return adb

    async def ensure_dir(self, device_id: str) -> None:
        adb = self._adb()
        serial = await self._serial(device_id)
        await _run(
            [adb, "-s", serial, "shell", "mkdir", "-p", DEVICE_GALLERY_DIR],
            timeout=8.0,
        )

    async def push(
        self,
        device_id: str,
        local_path: str,
        *,
        remote_name: str | None = None,
    ) -> str:
        """Push a single file to DCIM/Camera, return the device-side path."""
        if not os.path.isfile(local_path):
            raise FileNotFoundError(local_path)
        await self.ensure_dir(device_id)

        adb = self._adb()
        serial = await self._serial(device_id)

        if remote_name is None:
            ext = Path(local_path).suffix.lower() or ".jpg"
            remote_name = f"{PUSHED_PREFIX}{int(time.time() * 1000)}{ext}"
        remote_path = f"{DEVICE_GALLERY_DIR}/{remote_name}"

        code, out = await _run(
            [adb, "-s", serial, "push", local_path, remote_path],
            timeout=120.0,
        )
        if code != 0:
            raise RuntimeError(f"adb push failed: {out.strip()}")

        # Set a recent mtime so the file shows up at the top of the gallery.
        await _run(
            [adb, "-s", serial, "shell", "touch", remote_path],
            timeout=5.0,
        )

        # Tell MediaStore about the new file so it appears in the gallery.
        await _run(
            [
                adb, "-s", serial, "shell", "am", "broadcast",
                "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                "-d", f"file://{remote_path}",
            ],
            timeout=10.0,
        )
        return remote_path

    async def push_many(
        self, device_id: str, local_paths: list[str]
    ) -> list[str]:
        results: list[str] = []
        for idx, path in enumerate(local_paths):
            ext = Path(path).suffix.lower() or ".jpg"
            name = f"{PUSHED_PREFIX}{int(time.time() * 1000)}_{idx}{ext}"
            remote = await self.push(device_id, path, remote_name=name)
            results.append(remote)
            # small pause so timestamps differ and gallery ordering is stable
            await asyncio.sleep(0.2)
        return results

    async def cleanup_pushed(self, device_id: str) -> int:
        """Remove all files previously pushed by Chimera. Returns deleted count."""
        adb = self._adb()
        serial = await self._serial(device_id)
        pattern = f"{DEVICE_GALLERY_DIR}/{PUSHED_PREFIX}*"
        code, out = await _run(
            [adb, "-s", serial, "shell", "sh", "-c", f"ls {pattern} 2>/dev/null | wc -l"],
            timeout=5.0,
        )
        deleted = 0
        if code == 0:
            try:
                deleted = int(out.strip().splitlines()[-1].strip())
            except (ValueError, IndexError):
                deleted = 0
        await _run(
            [adb, "-s", serial, "shell", "sh", "-c", f"rm -f {pattern}"],
            timeout=10.0,
        )
        # re-trigger scan on the dir
        await _run(
            [
                adb, "-s", serial, "shell", "am", "broadcast",
                "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                "-d", f"file://{DEVICE_GALLERY_DIR}",
            ],
            timeout=8.0,
        )
        return deleted


gallery_service = GalleryService()
