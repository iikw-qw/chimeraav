"""PC AutoClicker — pyautogui-based clicker for desktop screen."""

from __future__ import annotations

import asyncio
import logging
import random

logger = logging.getLogger("chimera.pc_autoclicker")

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    _HAS_PYAUTOGUI = True
except ImportError:
    _HAS_PYAUTOGUI = False


class PCAutoClicker:
    def __init__(self) -> None:
        self.running = False

    async def run(
        self,
        clicks: int,
        x: int,
        y: int,
        area_w: int = 15,
        area_h: int = 10,
        delay_min: float = 8.0,
        delay_max: float = 13.0,
        mode: str = "photo",
    ) -> dict:
        if not _HAS_PYAUTOGUI:
            raise RuntimeError("pyautogui not installed")

        self.running = True
        results = {"done": 0, "errors": 0}

        for i in range(clicks):
            if not self.running:
                break
            try:
                tx = x + random.randint(-area_w, area_w)
                ty = y + random.randint(-area_h, area_h)
                pyautogui.moveTo(
                    tx, ty,
                    duration=random.uniform(0.3, 0.8),
                    tween=pyautogui.easeOutQuad,
                )
                await asyncio.sleep(random.uniform(0.05, 0.15))
                pyautogui.click()
                results["done"] += 1
            except Exception as e:
                logger.warning("PC click error: %s", e)
                results["errors"] += 1

            if mode == "photo":
                await asyncio.sleep(random.uniform(delay_min, delay_max))
            else:
                await asyncio.sleep(delay_min)

        self.running = False
        return results

    def stop(self) -> None:
        self.running = False

    @staticmethod
    def get_mouse_position() -> dict:
        if not _HAS_PYAUTOGUI:
            raise RuntimeError("pyautogui not installed")
        pos = pyautogui.position()
        return {"x": pos.x, "y": pos.y}
