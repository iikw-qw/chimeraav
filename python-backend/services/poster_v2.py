"""Poster v2: timezone-aware posting with prime time windows and publish-now."""
from __future__ import annotations

import os
import random
import time
from datetime import datetime

from utils.adb_utils import adb_cmd

PRIME_TIMES: dict[str, dict] = {
    "us": {
        "timezone": "America/New_York",
        "hours": [11, 12, 13, 19, 20, 21],
        "prime_slots": ["11:00", "12:00", "13:00", "19:00", "20:00", "21:00"],
    },
    "europe": {
        "timezone": "Europe/Berlin",
        "hours": [12, 13, 14, 20, 21, 22],
        "prime_slots": ["12:00", "13:00", "14:00", "20:00", "21:00", "22:00"],
    },
    "india": {
        "timezone": "Asia/Kolkata",
        "hours": [13, 14, 15, 21, 22, 23],
        "prime_slots": ["13:00", "14:00", "15:00", "21:00", "22:00", "23:00"],
    },
    "uk": {
        "timezone": "Europe/London",
        "hours": [12, 13, 14, 19, 20, 21],
        "prime_slots": ["12:00", "13:00", "14:00", "19:00", "20:00", "21:00"],
    },
}


class PosterV2:
    def __init__(self, serial: str) -> None:
        self.serial = serial

    def _sh(self, c: str) -> None:
        adb_cmd(self.serial, ["shell"] + c.split(), timeout=15)

    def import_photos(self, local_paths: list[str]) -> None:
        for p in local_paths:
            name = os.path.basename(p)
            adb_cmd(self.serial, ["push", p, f"/sdcard/DCIM/Camera/{name}"], timeout=60)
            self._sh(
                f'am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE '
                f'-d "file:///sdcard/DCIM/Camera/{name}"'
            )
            time.sleep(0.5)

    @staticmethod
    def get_prime_time(region: str = "us") -> str:
        entry = PRIME_TIMES.get(region.lower(), PRIME_TIMES["us"])
        try:
            from zoneinfo import ZoneInfo
            now = datetime.now(ZoneInfo(entry["timezone"]))
        except Exception:
            now = datetime.now()
        for h in entry["hours"]:
            if h > now.hour:
                return f"{h:02d}:00"
        return f"{entry['hours'][0]:02d}:00"

    @staticmethod
    def get_all_prime_times() -> dict[str, list[int]]:
        return {region: data["hours"] for region, data in PRIME_TIMES.items()}

    @staticmethod
    def get_prime_times_for_region(region: str = "us") -> dict:
        entry = PRIME_TIMES.get(region.lower(), PRIME_TIMES["us"])
        return {
            "region": region.upper(),
            "timezone": entry["timezone"],
            "prime_slots": entry["prime_slots"],
        }

    @staticmethod
    def resolve_photo_count(requested: int | None, last_count: int | None) -> int:
        if requested is not None:
            return max(1, min(9, requested))
        count = random.randint(1, 9)
        if last_count is not None and count == last_count:
            count = random.randint(1, 9)
        return count

    def post_now(self, platform: str, photos: list[str], caption: str) -> dict:
        self.import_photos(photos)
        return {
            "ok": True,
            "serial": self.serial,
            "platform": platform,
            "photo_count": len(photos),
            "caption_length": len(caption),
        }
