"""OCR / text recognition via WDA page source XML parsing."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

from app.services.action_logger import log_info

logger = logging.getLogger("chimera.ocr_service")


class OCRService:
    def __init__(self) -> None:
        self._ready = False

    async def load(self) -> bool:
        await log_info("ocr_load")
        self._ready = True
        await log_info("ocr_ready")
        return True

    @property
    def ready(self) -> bool:
        return self._ready

    async def recognize_from_page_source(
        self,
        udid: str,
        wda_port: int = 8100,
        device_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self._ready:
            await self.load()

        try:
            from app.services.ios_control import page_source

            source = await page_source(udid, wda_port)
            if not source:
                return []

            elements: list[dict[str, Any]] = []
            try:
                root = ET.fromstring(source)
                for elem in root.iter():
                    label = elem.get("label", "") or elem.get("name", "") or elem.get("value", "")
                    if label:
                        x = int(elem.get("x", 0))
                        y = int(elem.get("y", 0))
                        w = int(elem.get("width", 0))
                        h = int(elem.get("height", 0))
                        elements.append({
                            "text": label,
                            "type": elem.tag,
                            "bounds": {
                                "x1": x, "y1": y,
                                "x2": x + w, "y2": y + h,
                                "cx": x + w // 2, "cy": y + h // 2,
                            },
                        })
            except ET.ParseError:
                pass

            if elements:
                combined = ", ".join(e["text"] for e in elements[:5])
                await log_info("ocr_text_found", device_id=device_id,
                               text=combined[:200], count=len(elements))

            return elements

        except Exception as e:
            logger.error("Page source OCR failed for %s: %s", udid, e)
            return []

    async def find_text_on_screen(
        self,
        udid: str,
        target: str,
        wda_port: int = 8100,
        device_id: str | None = None,
    ) -> dict[str, Any] | None:
        texts = await self.recognize_from_page_source(udid, wda_port, device_id)
        target_lower = target.lower()
        for t in texts:
            if target_lower in t.get("text", "").lower():
                return t
        return None

    async def recognize_screen(
        self,
        udid: str,
        wda_port: int = 8100,
        device_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self.recognize_from_page_source(udid, wda_port, device_id)


ocr_service = OCRService()
