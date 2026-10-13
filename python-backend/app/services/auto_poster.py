"""Auto-poster — publish photos via ADB gallery flow.

BUG 4 FIX: full posting pipeline that pushes photos to the device gallery
and navigates the app UI to create a real post (same flow a human would do).

Steps:
  1. Push photos to /sdcard/DCIM/Camera via adb push
  2. Trigger MediaScanner so gallery indexes them
  3. Open the app → tap "New post" / "+"
  4. Select photo from gallery
  5. Next → enter caption → Share
  6. Verify publication
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import time
from typing import Any

from app.api._hub import hub
from app.services import tools as tools_svc
from app.services.antidetect import human_behavior
from app.services.platform_login import PlatformLogin, ELEMENTS

logger = logging.getLogger("chimera.auto_poster")

POSTING_ELEMENTS: dict[str, dict[str, Any]] = {
    "instagram": {
        "new_post": {
            "resource_ids": [
                "com.instagram.android:id/creation_tab",
                "com.instagram.android:id/tab_add",
            ],
            "texts": ["New post"],
            "content_descs": ["New post", "Create", "Создать"],
        },
        "gallery_grid": {
            "resource_ids": ["com.instagram.android:id/gallery_grid"],
        },
        "next_button": {
            "resource_ids": ["com.instagram.android:id/next_button_textview"],
            "texts": ["Next", "→", "Далее"],
        },
        "caption_field": {
            "resource_ids": ["com.instagram.android:id/caption_text_view"],
            "texts": ["Write a caption...", "Write a caption",
                      "Добавьте подпись...", "Add a caption"],
        },
        "share_button": {
            "resource_ids": [
                "com.instagram.android:id/share_button",
                "com.instagram.android:id/next_button_textview",
            ],
            "texts": ["Share", "Поделиться", "Опубликовать"],
        },
        "success_indicators": [
            "Your post has been shared", "shared", "posted", "Пост опубликован",
        ],
    },
    "facebook": {
        "new_post": {
            "texts": ["What's on your mind", "Что у вас нового", "Photo"],
        },
        "next_button": {
            "texts": ["Next", "Далее"],
        },
        "caption_field": {
            "texts": ["What's on your mind", "Say something about this photo"],
        },
        "share_button": {
            "texts": ["Post", "Publish", "Опубликовать"],
        },
        "success_indicators": ["posted", "shared"],
    },
    "tiktok": {
        "new_post": {
            "texts": ["+", "Create"],
            "content_descs": ["Create", "Создать", "Record"],
        },
        "next_button": {
            "texts": ["Next", "Далее"],
        },
        "caption_field": {
            "texts": ["Describe your video", "Add a description"],
        },
        "share_button": {
            "texts": ["Post", "Publish"],
        },
        "success_indicators": ["posted", "uploaded"],
    },
}


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
    return proc.returncode or 0, stdout.decode("utf-8", errors="replace")


class AutoPoster:
    def __init__(self, serial: str, platform: str):
        self.serial = serial
        self.platform = platform
        self.login_svc = PlatformLogin(serial)
        self._adb_path: str | None = None

    @property
    def adb(self) -> str:
        if self._adb_path is None:
            self._adb_path = tools_svc.resolve("adb") or "adb"
        return self._adb_path

    async def _adb_shell(self, cmd: str) -> str:
        code, out = await _run(
            [self.adb, "-s", self.serial, "shell", cmd], timeout=15.0,
        )
        return out

    async def _adb_host(self, cmd: str) -> str:
        code, out = await _run(
            [self.adb, "-s", self.serial] + cmd.split(), timeout=120.0,
        )
        return out

    async def _ui_dump(self) -> str:
        await _run(
            [self.adb, "-s", self.serial, "shell",
             "uiautomator", "dump", "/sdcard/ui.xml"],
            timeout=10.0,
        )
        code, xml = await _run(
            [self.adb, "-s", self.serial, "shell", "cat", "/sdcard/ui.xml"],
            timeout=5.0,
        )
        return xml if code == 0 else ""

    async def _find_with_retry(self, element_config: dict,
                                timeout: float = 10.0) -> dict | None:
        start = time.time()
        while time.time() - start < timeout:
            xml = await self._ui_dump()
            result = self.login_svc._find_element(xml, element_config)
            if result:
                return result
            await asyncio.sleep(1)
        return None

    async def _tap(self, x: int, y: int, *, device_id: str | None = None) -> None:
        jx, jy = human_behavior.jittered_tap(x, y)
        press = human_behavior.tap_press_ms()
        if device_id:
            try:
                await hub.broadcast("cursor", {
                    "device_id": device_id, "kind": "tap",
                    "x": jx, "y": jy, "duration_ms": press,
                })
            except Exception:
                pass
        await _run(
            [self.adb, "-s", self.serial, "shell", "input", "swipe",
             str(jx), str(jy), str(jx), str(jy), str(press)],
            timeout=6.0,
        )

    async def _type_text(self, text: str) -> None:
        plan = human_behavior.typing_plan(text)
        for ch, delay in plan:
            if ch == " ":
                safe = "%s"
            elif ch in ("'", '"', "\\", "`", "&", ";", "<", ">", "|", "$"):
                safe = f"\\{ch}"
            else:
                safe = ch
            await _run(
                [self.adb, "-s", self.serial, "shell", "input", "text", safe],
                timeout=4.0,
            )
            await asyncio.sleep(delay)

    async def post(self, photo_paths: list[str], caption: str,
                   *, device_id: str | None = None) -> dict:
        platform_cfg = ELEMENTS.get(self.platform, {})
        posting_cfg = POSTING_ELEMENTS.get(self.platform, {})
        package = platform_cfg.get("package", "")

        if not package:
            return {"success": False, "error": f"Пакет для {self.platform} не найден"}

        for photo in photo_paths:
            if not os.path.isfile(photo):
                return {"success": False, "error": f"Файл не найден: {photo}"}

        remote_paths = []
        for photo in photo_paths:
            filename = os.path.basename(photo)
            remote = f"/sdcard/DCIM/Camera/chimera_{int(time.time()*1000)}_{filename}"
            await _run(
                [self.adb, "-s", self.serial, "push", photo, remote],
                timeout=60.0,
            )
            await self._adb_shell(
                f'am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE '
                f'-d "file://{remote}"'
            )
            remote_paths.append(remote)
            await asyncio.sleep(1)

        await asyncio.sleep(2)

        await self._adb_shell(
            f"monkey -p {package} -c android.intent.category.LAUNCHER 1"
        )
        await asyncio.sleep(4)

        if "new_post" in posting_cfg:
            new_post = await self._find_with_retry(posting_cfg["new_post"], timeout=10)
            if not new_post:
                return {"success": False, "error": "Кнопка создания поста не найдена"}
            await self._tap(new_post["x"], new_post["y"], device_id=device_id)
            await asyncio.sleep(3)

        await asyncio.sleep(2)
        if "gallery_grid" in posting_cfg:
            xml = await self._ui_dump()
            gallery = self.login_svc._find_element(xml, posting_cfg["gallery_grid"])
            if gallery:
                await self._tap(
                    gallery["x"] - gallery.get("w", 200) // 2 + 60,
                    gallery["y"] - gallery.get("h", 200) // 2 + 60,
                    device_id=device_id,
                )
            else:
                await self._tap(200, 600, device_id=device_id)
        else:
            await self._tap(200, 600, device_id=device_id)
        await asyncio.sleep(2)

        if "next_button" in posting_cfg:
            next_btn = await self._find_with_retry(posting_cfg["next_button"], timeout=8)
            if next_btn:
                await self._tap(next_btn["x"], next_btn["y"], device_id=device_id)
            else:
                return {"success": False, "error": "Кнопка Next не найдена"}
            await asyncio.sleep(3)

            next_btn2 = await self._find_with_retry(posting_cfg["next_button"], timeout=5)
            if next_btn2:
                await self._tap(next_btn2["x"], next_btn2["y"], device_id=device_id)
                await asyncio.sleep(3)

        if "caption_field" in posting_cfg:
            caption_field = await self._find_with_retry(
                posting_cfg["caption_field"], timeout=8,
            )
            if caption_field:
                await self._tap(caption_field["x"], caption_field["y"],
                                device_id=device_id)
                await asyncio.sleep(0.5)
                await self._type_text(caption)
            else:
                return {"success": False, "error": "Поле подписи не найдено"}
            await asyncio.sleep(1)

        if "share_button" in posting_cfg:
            share_btn = await self._find_with_retry(
                posting_cfg["share_button"], timeout=8,
            )
            if share_btn:
                await self._tap(share_btn["x"], share_btn["y"], device_id=device_id)
            else:
                return {"success": False, "error": "Кнопка Share не найдена"}

        await asyncio.sleep(10)

        xml = await self._ui_dump()
        screen_text = " ".join(re.findall(r'text="([^"]*)"', xml)).lower()
        indicators = posting_cfg.get("success_indicators", [])
        if any(ind.lower() in screen_text for ind in indicators):
            await self._notify(device_id, True, f"Пост опубликован в {self.platform}")
            return {"success": True, "method": "adb_automation"}

        home_indicators = platform_cfg.get("home_indicators", [])
        if any(ind.lower() in screen_text for ind in home_indicators):
            await self._notify(device_id, True, f"Пост опубликован в {self.platform}")
            return {"success": True, "method": "adb_automation"}

        await self._notify(device_id, False,
                           "Не удалось подтвердить публикацию — проверь экран")
        return {"success": False,
                "error": "Не удалось подтвердить публикацию — проверь экран"}

    async def _notify(self, device_id: str | None, success: bool,
                      message: str) -> None:
        try:
            await hub.broadcast("notifications", {
                "level": "success" if success else "danger",
                "title": "Автопостинг" if success else "Ошибка публикации",
                "message": message,
                "device_id": device_id,
            })
        except Exception:
            pass
