"""DM Scanner — scan DMs across platforms, classify gender, mute non-male contacts."""
from __future__ import annotations

import asyncio
import logging
import re
import time

from utils.adb_utils import adb_cmd
from services.ui_finder import find_element

logger = logging.getLogger(__name__)

PLATFORM_CONFIG = {
    "instagram": {
        "pkg": "com.instagram.android",
        "dm_hints": ["direct", "DM", "messages icon"],
        "home_hints": ["Home"],
    },
    "tiktok": {
        "pkg": "com.zhiliaoapp.musically",
        "dm_hints": ["inbox", "messages"],
        "home_hints": ["Home", "For You"],
    },
    "facebook": {
        "pkg": "com.facebook.orca",
        "dm_hints": ["messenger", "chat"],
        "home_hints": ["Home"],
    },
    "twitter": {
        "pkg": "com.twitter.android",
        "dm_hints": ["messages", "DM", "envelope"],
        "home_hints": ["Home"],
    },
    "threads": {
        "pkg": "com.instagram.barcelona",
        "dm_hints": ["activity", "messages"],
        "home_hints": ["Home"],
    },
}

try:
    import gender_guesser.detector as gender_lib
    _detector = gender_lib.Detector()
except Exception:
    _detector = None

_contacts_db: list[dict] = []


def _classify_gender(username: str) -> str:
    first_name = _extract_first_name(username)
    if _detector and first_name:
        result = _detector.get_gender(first_name)
        if result in ("male", "mostly_male"):
            return "male"
        if result in ("female", "mostly_female"):
            return "female"
        return "unknown"
    name = username.lower()
    female_endings = ("ova", "eva", "ina", "aya")
    male_endings = ("ov", "ev", "in")
    for e in female_endings:
        if name.endswith(e):
            return "female"
    for e in male_endings:
        if name.endswith(e):
            return "male"
    return "unknown"


def _extract_first_name(username: str) -> str:
    clean = re.sub(r"[._\d]+", " ", username).strip()
    parts = clean.split()
    return parts[0].capitalize() if parts else ""


def _sh(serial: str, cmd: str) -> str:
    try:
        return adb_cmd(serial, ["shell"] + cmd.split(), timeout=10).stdout.strip()
    except Exception:
        return ""


class DMScanner:
    def __init__(self, serial: str, platform: str = "instagram") -> None:
        self.serial = serial
        self.platform = platform
        self.cfg = PLATFORM_CONFIG.get(platform, PLATFORM_CONFIG["instagram"])

    async def _navigate_to_dms(self) -> bool:
        pkg = self.cfg["pkg"]
        _sh(self.serial, f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
        await asyncio.sleep(3)
        btn = find_element(self.serial, self.cfg["dm_hints"])
        if btn:
            _sh(self.serial, f"input tap {btn['x']} {btn['y']}")
            await asyncio.sleep(2)
            return True
        return False

    async def scan_dms(self) -> list[dict]:
        await self._navigate_to_dms()
        _sh(self.serial, "uiautomator dump /sdcard/u.xml")
        xml = _sh(self.serial, "cat /sdcard/u.xml")

        skip = {"messages", "search", "direct", "inbox", "general", "primary",
                "requests", "message requests"}
        results = []
        for m in re.finditer(r'text="([^"]+)"', xml):
            username = m.group(1)
            if not username or len(username) < 2 or username.lower() in skip:
                continue
            results.append({"username": username, "platform": self.platform})
            if len(results) >= 15:
                break

        btn = find_element(self.serial, self.cfg["home_hints"])
        if btn:
            _sh(self.serial, f"input tap {btn['x']} {btn['y']}")
        await asyncio.sleep(1)
        return results

    async def _mute_conversation(self, username: str) -> bool:
        try:
            _sh(self.serial, "uiautomator dump /sdcard/u.xml")
            xml = _sh(self.serial, "cat /sdcard/u.xml")
            pat = f'text="{re.escape(username)}"[^>]*bounds="\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]"'
            match = re.search(pat, xml, re.IGNORECASE)
            if not match:
                return False
            x = (int(match.group(1)) + int(match.group(3))) // 2
            y = (int(match.group(2)) + int(match.group(4))) // 2
            _sh(self.serial, f"input swipe {x} {y} {x} {y} 1500")
            await asyncio.sleep(1.5)
            mute_btn = find_element(self.serial, ["Mute", "mute", "Без звука"])
            if mute_btn:
                _sh(self.serial, f"input tap {mute_btn['x']} {mute_btn['y']}")
                await asyncio.sleep(1)
                logger.info("Muted %s on %s", username, self.platform)
                return True
            _sh(self.serial, "input keyevent KEYCODE_BACK")
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error("Mute failed for %s: %s", username, e)
        return False

    async def process_dms(self) -> dict:
        dms = await self.scan_dms()
        results: dict[str, list] = {"male": [], "female": [], "unknown": []}
        for dm in dms:
            gender = _classify_gender(dm["username"])
            dm["gender"] = gender
            dm["muted"] = False

            existing = next(
                (c for c in _contacts_db
                 if c["serial"] == self.serial
                 and c["platform"] == self.platform
                 and c["username"] == dm["username"]),
                None,
            )
            if existing:
                existing["last_message"] = ""
                existing["scanned_at"] = time.time()
            else:
                _contacts_db.append({
                    "serial": self.serial,
                    "platform": self.platform,
                    "username": dm["username"],
                    "gender": gender,
                    "last_message": "",
                    "scanned_at": time.time(),
                    "muted": False,
                })

            if gender in ("female", "unknown"):
                muted = await self._mute_conversation(dm["username"])
                dm["muted"] = muted
                if existing:
                    existing["muted"] = muted

            results[gender].append(dm)

        return {**results, "total": len(dms)}


def get_contacts(serial: str | None = None, platform: str | None = None,
                 gender: str | None = None) -> list[dict]:
    result = _contacts_db
    if serial:
        result = [c for c in result if c["serial"] == serial]
    if platform:
        result = [c for c in result if c["platform"] == platform]
    if gender:
        result = [c for c in result if c["gender"] == gender]
    return result


def export_contacts(fmt: str = "json") -> list[dict] | str:
    if fmt == "csv":
        lines = ["serial,platform,username,gender,muted,scanned_at"]
        for c in _contacts_db:
            lines.append(f"{c['serial']},{c['platform']},{c['username']},{c['gender']},{c['muted']},{c['scanned_at']}")
        return "\n".join(lines)
    return _contacts_db
