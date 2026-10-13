"""Robust UI element finder via uiautomator XML dump.

Solves the 'invisible buttons' problem by:
- Node-by-node XML parsing with all attribute filters
- Case-insensitive and partial text matching
- content-description fallback
- XML cache to avoid spamming adb
- wait_find with polling for elements that load late
"""

from __future__ import annotations

import asyncio
import logging
import re
import time

logger = logging.getLogger("chimera.ui_finder")


async def _run(cmd: list[str], timeout: float = 10.0) -> tuple[int, str]:
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


class UIFinder:
    def __init__(self, serial: str, adb: str = "adb"):
        self.serial = serial
        self.adb = adb
        self._xml_cache = ""
        self._cache_time = 0.0

    async def _dump(self, force: bool = False) -> str:
        now = time.time()
        if not force and self._xml_cache and now - self._cache_time < 0.5:
            return self._xml_cache
        try:
            await _run(
                [self.adb, "-s", self.serial, "shell",
                 "uiautomator", "dump", "/sdcard/ui.xml"],
                timeout=8.0,
            )
            code, xml = await _run(
                [self.adb, "-s", self.serial, "shell", "cat", "/sdcard/ui.xml"],
                timeout=5.0,
            )
            if code == 0:
                self._xml_cache = xml
                self._cache_time = now
        except Exception as e:
            logger.warning("UI dump failed: %s", e)
        return self._xml_cache

    @staticmethod
    def _parse_bounds(bounds_str: str) -> dict | None:
        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
        if not m:
            return None
        x1, y1, x2, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        return {"x": (x1 + x2) // 2, "y": (y1 + y2) // 2, "w": x2 - x1, "h": y2 - y1}

    async def find(
        self,
        *,
        resource_id: str | None = None,
        text: str | None = None,
        text_contains: str | None = None,
        content_desc: str | None = None,
        class_name: str | None = None,
        index: int | None = None,
        clickable: bool | None = None,
    ) -> dict | None:
        xml = await self._dump(force=True)
        if xml:
            result = self._find_in_xml(
                xml,
                resource_id=resource_id,
                text=text,
                text_contains=text_contains,
                content_desc=content_desc,
                class_name=class_name,
                index=index,
                clickable=clickable,
            )
            if result:
                return result

        search_texts: list[str] = []
        if text:
            search_texts.append(text)
        if text_contains:
            search_texts.append(text_contains)
        if search_texts:
            return await self.find_by_screenshot(ocr_texts=search_texts)

        return None

    @staticmethod
    def _find_in_xml(
        xml: str,
        *,
        resource_id: str | None = None,
        text: str | None = None,
        text_contains: str | None = None,
        content_desc: str | None = None,
        class_name: str | None = None,
        index: int | None = None,
        clickable: bool | None = None,
    ) -> dict | None:
        nodes = re.findall(r"<node\s([^>]+?)/?>", xml)
        class_count = 0

        for node_attrs in nodes:
            attrs: dict[str, str] = {}
            for attr_m in re.finditer(r'(\w[\w-]*)="([^"]*)"', node_attrs):
                attrs[attr_m.group(1)] = attr_m.group(2)

            if resource_id and attrs.get("resource-id") != resource_id:
                continue
            if text and attrs.get("text", "").lower() != text.lower():
                continue
            if text_contains and text_contains.lower() not in attrs.get("text", "").lower():
                continue
            if content_desc and content_desc.lower() not in attrs.get("content-desc", "").lower():
                continue
            if class_name and attrs.get("class") != class_name:
                if index is not None:
                    continue
                else:
                    continue
            if class_name and index is not None:
                if attrs.get("class") == class_name:
                    if class_count != index:
                        class_count += 1
                        continue
                    class_count += 1
                else:
                    continue
            if clickable is not None:
                if attrs.get("clickable") != str(clickable).lower():
                    continue

            bounds_str = attrs.get("bounds", "")
            result = UIFinder._parse_bounds(bounds_str)
            if result:
                result["text"] = attrs.get("text", "")
                result["resource_id"] = attrs.get("resource-id", "")
                result["class"] = attrs.get("class", "")
                result["desc"] = attrs.get("content-desc", "")
                return result
        return None

    async def find_any(self, candidates: list[dict]) -> dict | None:
        for c in candidates:
            result = await self.find(**c)
            if result:
                return result
        return None

    async def wait_find(self, candidates: list[dict], timeout: float = 15.0) -> dict | None:
        start = time.time()
        while time.time() - start < timeout:
            result = await self.find_any(candidates)
            if result:
                return result
            await asyncio.sleep(0.8)
        return None

    async def get_all_text(self) -> str:
        xml = await self._dump(force=True)
        return " ".join(re.findall(r'text="([^"]*)"', xml))

    async def has_text(self, texts: list[str]) -> bool:
        screen = (await self.get_all_text()).lower()
        return any(t.lower() in screen for t in texts)

    async def find_by_screenshot(
        self,
        button_templates: list[str] | None = None,
        ocr_texts: list[str] | None = None,
    ) -> dict | None:
        """Pixel-level fallback when uiautomator dump misses elements."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            remote = "/sdcard/chimera_screen.png"
            local = f"{td}/screen.png"
            await _run([self.adb, "-s", self.serial, "shell", "screencap", "-p", remote], timeout=10)
            await _run([self.adb, "-s", self.serial, "pull", remote, local], timeout=10)

            try:
                import cv2
                import numpy as np
            except ImportError:
                logger.debug("opencv not available for screenshot fallback")
                return None

            screen = cv2.imread(local)
            if screen is None:
                return None
            gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

            if button_templates:
                for tmpl_path in button_templates:
                    tmpl = cv2.imread(tmpl_path, 0)
                    if tmpl is None:
                        continue
                    res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(res)
                    if max_val > 0.75:
                        h, w = tmpl.shape
                        return {"x": max_loc[0] + w // 2, "y": max_loc[1] + h // 2,
                                "confidence": float(max_val)}

            if ocr_texts:
                try:
                    import pytesseract
                    data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
                    for i, word in enumerate(data["text"]):
                        if data["conf"][i] < 40:
                            continue
                        for search in ocr_texts:
                            if search.lower() in word.lower():
                                x = data["left"][i] + data["width"][i] // 2
                                y = data["top"][i] + data["height"][i] // 2
                                return {"x": x, "y": y, "text": word,
                                        "confidence": data["conf"][i]}
                except ImportError:
                    logger.debug("pytesseract not available")

        return None
