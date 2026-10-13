"""
UIFinder — каскадный поиск UI-элементов на Android через ADB.
Уровень 1: uiautomator XML dump + фильтрация по атрибутам.
Уровень 2: скриншот + OCR (pytesseract fallback).
"""

import subprocess
import re
import time
import asyncio
import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class UIFinder:
    def __init__(self, serial: str):
        self.serial = serial

    def _adb(self, cmd) -> str:
        r = subprocess.run(
            ["adb", "-s", self.serial, "shell", cmd],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout

    def _dump_xml(self) -> str:
        self._adb("uiautomator dump /sdcard/w.xml")
        return self._adb("cat /sdcard/w.xml")

    def _screenshot_cv(self):
        self._adb("screencap -p /sdcard/s.png")
        subprocess.run(
            ["adb", "-s", self.serial, "pull", "/sdcard/s.png", "/tmp/s.png"],
            capture_output=True, timeout=10,
        )
        return cv2.imread("/tmp/s.png")

    def find(self, **kwargs) -> dict | None:
        xml = self._dump_xml()
        if xml:
            result = self._search_xml(xml, **kwargs)
            if result:
                return result

        search = kwargs.get("text") or kwargs.get("text_contains")
        if search:
            result = self._search_ocr(search)
            if result:
                return result

        return None

    def _search_xml(
        self, xml, resource_id=None, text=None, text_contains=None,
        content_desc=None, class_name=None, index=None, **_,
    ) -> dict | None:
        nodes = re.findall(r'<node\s([^>]+?)/?>', xml, re.DOTALL)
        match_index = 0
        for node in nodes:
            attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', node))
            if resource_id and attrs.get("resource-id", "") != resource_id:
                continue
            if text and attrs.get("text", "").lower() != text.lower():
                continue
            if text_contains and text_contains.lower() not in attrs.get("text", "").lower():
                continue
            if content_desc and content_desc.lower() not in attrs.get("content-desc", "").lower():
                continue
            if class_name and attrs.get("class", "") != class_name:
                continue
            if index is not None:
                if match_index != index:
                    match_index += 1
                    continue
            bounds = re.match(
                r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', attrs.get("bounds", ""),
            )
            if bounds:
                x1, y1, x2, y2 = map(int, bounds.groups())
                return {
                    "x": (x1 + x2) // 2, "y": (y1 + y2) // 2,
                    "w": x2 - x1, "h": y2 - y1,
                    "text": attrs.get("text", ""),
                    "rid": attrs.get("resource-id", ""),
                }
        return None

    def _search_ocr(self, search_text: str) -> dict | None:
        try:
            import pytesseract
            img = self._screenshot_cv()
            if img is None:
                return None
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            d = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
            for i, word in enumerate(d["text"]):
                if d["conf"][i] < 40:
                    continue
                if search_text.lower() in word.lower():
                    return {
                        "x": d["left"][i] + d["width"][i] // 2,
                        "y": d["top"][i] + d["height"][i] // 2,
                        "text": word,
                    }
        except Exception:
            pass
        return None

    def find_any(self, candidates: list[dict]) -> dict | None:
        for c in candidates:
            r = self.find(**c)
            if r:
                return r
        return None

    async def wait(self, candidates: list[dict], timeout=15) -> dict | None:
        start = time.time()
        while time.time() - start < timeout:
            r = self.find_any(candidates)
            if r:
                return r
            await asyncio.sleep(0.7)
        return None

    def get_text(self) -> str:
        xml = self._dump_xml()
        return " ".join(re.findall(r'text="([^"]*)"', xml))

    def has_any(self, texts: list[str]) -> bool:
        screen = self.get_text().lower()
        return any(t.lower() in screen for t in texts)
