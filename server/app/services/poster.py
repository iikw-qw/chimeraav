"""
Автопостинг: импорт фото с ПК на телефон, публикация с человеческим курсором.
Зависит от: human_cursor, ui_finder, adb_proxy
"""

import asyncio
import os
import subprocess
import random
import logging
from typing import Dict, Any, List, Optional

from app.services.human_cursor import HumanCursor
from app.services.ui_finder import UIFinder

logger = logging.getLogger(__name__)

PLATFORM_PACKAGES = {
    "instagram": "com.instagram.android",
    "tiktok": "com.zhiliaoapp.musically",
    "facebook": "com.facebook.katana",
    "twitter": "com.twitter.android",
}


class Poster:
    def __init__(self, serial: str):
        self.serial = serial
        self.cursor = HumanCursor(serial)
        self.ui = UIFinder(serial)

    def _sh(self, cmd: str) -> str:
        try:
            r = subprocess.run(
                ["adb", "-s", self.serial, "shell", cmd],
                capture_output=True, text=True, timeout=15,
            )
            return r.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    def _push(self, local_path: str, remote_path: str) -> bool:
        try:
            r = subprocess.run(
                ["adb", "-s", self.serial, "push", local_path, remote_path],
                capture_output=True, timeout=60,
            )
            return r.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    async def post(
        self,
        photo_paths: List[str],
        caption: str,
        platform: str = "instagram",
    ) -> Dict[str, Any]:
        for p in photo_paths:
            name = os.path.basename(p)
            remote = f"/sdcard/DCIM/Camera/{name}"
            if not self._push(p, remote):
                return {"ok": False, "err": f"Failed to push {name}"}
            self._sh(
                f'am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE '
                f'-d "file://{remote}"'
            )
            await asyncio.sleep(1)
        await asyncio.sleep(2)

        pkg = PLATFORM_PACKAGES.get(platform, PLATFORM_PACKAGES["instagram"])
        self._sh(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
        await asyncio.sleep(4)

        btn = await self.ui.wait(
            [
                {"content_desc": "New post"},
                {"text": "New post"},
                {"resource_id": "com.instagram.android:id/creation_tab"},
            ],
            timeout=10,
        )
        if btn:
            self.cursor.tap(btn["x"], btn["y"])
        else:
            return {"ok": False, "err": "New Post button not found"}
        await asyncio.sleep(3)

        await asyncio.sleep(2)
        self.cursor.tap(200, 600)
        await asyncio.sleep(2)

        nx = await self.ui.wait([{"text": "Next"}, {"text": "Далее"}], timeout=8)
        if nx:
            self.cursor.tap(nx["x"], nx["y"])
        await asyncio.sleep(3)

        nx2 = await self.ui.wait([{"text": "Next"}, {"text": "Далее"}], timeout=5)
        if nx2:
            self.cursor.tap(nx2["x"], nx2["y"])
        await asyncio.sleep(3)

        cap = await self.ui.wait(
            [
                {"text": "Write a caption..."},
                {"text_contains": "caption"},
                {"resource_id": "com.instagram.android:id/caption_text_view"},
            ],
            timeout=8,
        )
        if cap:
            self.cursor.tap(cap["x"], cap["y"])
            await asyncio.sleep(0.3)
            self.cursor.type_text(caption)
        await asyncio.sleep(1)

        sh = await self.ui.wait([{"text": "Share"}, {"text": "Опубликовать"}], timeout=8)
        if sh:
            self.cursor.tap(sh["x"], sh["y"])
        else:
            self._sh("input keyevent 66")
        await asyncio.sleep(8)

        return {"ok": True, "platform": platform, "photos": len(photo_paths)}
