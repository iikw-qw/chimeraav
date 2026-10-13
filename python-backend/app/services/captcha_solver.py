"""Captcha detection and solving — local checkbox click + 2Captcha API fallback."""

from __future__ import annotations

import asyncio
import base64
import logging
import tempfile

import httpx

from app.services import tools as tools_svc
from app.services.human_cursor import ADBHumanCursor
from app.services.ui_finder import UIFinder

logger = logging.getLogger("chimera.captcha")

_CAPTCHA_SIGNS = [
    "captcha", "verify", "robot", "human", "select all",
    "pick the", "choose", "tap the", "security check",
    "подтвердите", "выберите", "нажмите на",
]


class CaptchaSolver:
    def __init__(self, serial: str, api_key: str = ""):
        adb = tools_svc.resolve("adb") or "adb"
        self.serial = serial
        self.api_key = api_key
        self.cursor = ADBHumanCursor(serial)
        self.ui = UIFinder(serial, adb=adb)

    async def detect_captcha(self) -> dict | None:
        screen_text = (await self.ui.get_all_text()).lower()
        for sign in _CAPTCHA_SIGNS:
            if sign in screen_text:
                return {"type": "detected", "text": sign}

        recaptcha = await self.ui.find(text_contains="I'm not a robot")
        if recaptcha:
            return {"type": "recaptcha_checkbox", "element": recaptcha}

        hcaptcha = await self.ui.find(text_contains="hCaptcha")
        if hcaptcha:
            return {"type": "hcaptcha", "element": hcaptcha}

        return None

    async def solve(self) -> bool:
        captcha = await self.detect_captcha()
        if not captcha:
            return True

        logger.info("Captcha detected: %s", captcha["type"])

        if captcha["type"] == "recaptcha_checkbox":
            el = captcha["element"]
            self.cursor.human_tap(el["x"], el["y"])
            await asyncio.sleep(3)
            if not await self.detect_captcha():
                logger.info("Captcha solved via checkbox")
                return True

        if self.api_key:
            return await self._solve_via_2captcha()

        logger.warning("Captcha not solved — manual input required")
        return False

    async def _solve_via_2captcha(self) -> bool:
        adb = tools_svc.resolve("adb") or "adb"
        with tempfile.TemporaryDirectory() as td:
            remote = "/sdcard/captcha_tmp.png"
            local = f"{td}/captcha.png"
            proc = await asyncio.create_subprocess_exec(
                adb, "-s", self.serial, "shell", "screencap", "-p", remote,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10)
            proc2 = await asyncio.create_subprocess_exec(
                adb, "-s", self.serial, "pull", remote, local,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc2.communicate(), timeout=10)

            try:
                with open(local, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
            except FileNotFoundError:
                return False

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post("http://2captcha.com/in.php", data={
                "key": self.api_key, "method": "base64",
                "body": img_b64, "json": "1",
            })
            data = resp.json()
            if data.get("status") != 1:
                return False
            task_id = data["request"]

            for _ in range(20):
                await asyncio.sleep(3)
                resp = await client.get("http://2captcha.com/res.php", params={
                    "key": self.api_key, "action": "get",
                    "id": task_id, "json": "1",
                })
                data = resp.json()
                if data.get("status") == 1:
                    answer = data["request"]
                    code_field = await self.ui.find(class_name="android.widget.EditText")
                    if code_field:
                        self.cursor.human_tap(code_field["x"], code_field["y"])
                        await asyncio.sleep(0.3)
                        self.cursor.human_type(answer)
                        await asyncio.sleep(0.5)
                        confirm = await self.ui.find_any([
                            {"text": "Verify"}, {"text": "Submit"},
                            {"text": "Continue"}, {"text": "Подтвердить"},
                            {"text": "OK"},
                        ])
                        if confirm:
                            self.cursor.human_tap(confirm["x"], confirm["y"])
                        else:
                            proc3 = await asyncio.create_subprocess_exec(
                                adb, "-s", self.serial, "shell",
                                "input", "keyevent", "66",
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                            )
                            await proc3.communicate()
                    await asyncio.sleep(3)
                    logger.info("Captcha solved via 2Captcha")
                    return True
                if "CAPCHA_NOT_READY" not in str(data.get("request", "")):
                    return False
        return False
