"""AutoClicker — automated button clicking with captcha bypass.

Two modes:
  - photo (batch): click N times with random delay
  - sequential: click → wait for completion → click again
"""

from __future__ import annotations

import asyncio
import logging
import random
import time

from app.services import tools as tools_svc
from app.services.captcha_solver import CaptchaSolver
from app.services.human_cursor import ADBHumanCursor
from app.services.ui_finder import UIFinder

logger = logging.getLogger("chimera.autoclicker")


class AutoClicker:
    def __init__(self, serial: str, captcha_api_key: str = ""):
        adb = tools_svc.resolve("adb") or "adb"
        self.serial = serial
        self.cursor = ADBHumanCursor(serial)
        self.ui = UIFinder(serial, adb=adb)
        self.captcha = CaptchaSolver(serial, captcha_api_key)
        self.running = False

    async def click_at_button(
        self,
        button_text: str | None = None,
        x: int | None = None,
        y: int | None = None,
        area_w: int = 20,
        area_h: int = 10,
    ) -> bool:
        if button_text:
            el = await self.ui.find_any([
                {"text": button_text},
                {"text_contains": button_text},
                {"content_desc": button_text},
            ])
            if el:
                tx = el["x"] + random.randint(-area_w // 2, area_w // 2)
                ty = el["y"] + random.randint(-area_h // 2, area_h // 2)
                self.cursor.human_tap(tx, ty)
                return True
            return False
        if x is not None and y is not None:
            tx = x + random.randint(-area_w // 2, area_w // 2)
            ty = y + random.randint(-area_h // 2, area_h // 2)
            self.cursor.human_tap(tx, ty)
            return True
        return False

    async def run_photo_mode(
        self,
        button_text: str,
        count: int,
        delay_min: float = 8,
        delay_max: float = 13,
        vectors: list[dict] | None = None,
    ) -> dict:
        self.running = True
        results = {"clicks": 0, "captchas_solved": 0, "errors": 0}

        for i in range(count):
            if not self.running:
                break
            captcha = await self.captcha.detect_captcha()
            if captcha:
                solved = await self.captcha.solve()
                if solved:
                    results["captchas_solved"] += 1
                    await asyncio.sleep(2)
                else:
                    results["errors"] += 1
                    continue

            if vectors:
                v = vectors[i % len(vectors)]
                clicked = await self.click_at_button(
                    button_text=button_text,
                    x=v.get("x"), y=v.get("y"),
                    area_w=v.get("area_w", 20), area_h=v.get("area_h", 10),
                )
            else:
                clicked = await self.click_at_button(button_text=button_text)

            if clicked:
                results["clicks"] += 1
            else:
                results["errors"] += 1

            await asyncio.sleep(random.uniform(delay_min, delay_max))

        self.running = False
        return results

    async def run_sequential_mode(
        self,
        button_text: str,
        count: int,
        wait_for_completion: str | None = None,
        vectors: list[dict] | None = None,
    ) -> dict:
        self.running = True
        results = {"clicks": 0, "captchas_solved": 0, "errors": 0}

        for i in range(count):
            if not self.running:
                break
            captcha = await self.captcha.detect_captcha()
            if captcha:
                solved = await self.captcha.solve()
                if solved:
                    results["captchas_solved"] += 1
                    await asyncio.sleep(2)
                else:
                    results["errors"] += 1
                    continue

            if vectors:
                v = vectors[i % len(vectors)]
                await self.click_at_button(
                    button_text=button_text,
                    x=v.get("x"), y=v.get("y"),
                    area_w=v.get("area_w", 20), area_h=v.get("area_h", 10),
                )
            else:
                await self.click_at_button(button_text=button_text)
            results["clicks"] += 1

            if wait_for_completion:
                await self._wait_for_element(wait_for_completion, timeout=120)
            else:
                await asyncio.sleep(2)
                for _ in range(60):
                    btn = await self.ui.find_any([
                        {"text": button_text},
                        {"text_contains": button_text},
                    ])
                    if btn:
                        break
                    await asyncio.sleep(2)

            await asyncio.sleep(random.uniform(1, 3))

        self.running = False
        return results

    async def _wait_for_element(self, text: str, timeout: float = 120) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            if await self.ui.find_any([{"text": text}, {"text_contains": text}]):
                return True
            await asyncio.sleep(2)
        return False

    def stop(self) -> None:
        self.running = False
