"""UIFinder v2 — UIAutomator dump + OCR fallback + SQLite cache."""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta

from utils.adb_utils import adb_cmd

logger = logging.getLogger(__name__)

BUTTON_MAP: dict[str, dict[str, list[str]]] = {
    "instagram": {
        "like_button": ["like", "heart", "com.instagram.android:id/like_button"],
        "story_ring": ["story", "com.instagram.android:id/reel_viewer_root"],
        "profile_link": ["profile", "com.instagram.android:id/row_profile_header"],
        "next_button": ["next", "com.instagram.android:id/next_button"],
        "share_button": ["share", "com.instagram.android:id/action_bar_button_action"],
        "reply_field": ["reply", "message", "com.instagram.android:id/reply_text_input"],
        "follow_button": ["follow", "com.instagram.android:id/button_follow"],
        "search_tab": ["search", "Search and explore", "com.instagram.android:id/search_tab"],
    },
    "tiktok": {
        "like_button": ["like", "com.zhiliaoapp.musically:id/like"],
        "profile_link": ["com.zhiliaoapp.musically:id/avatar"],
        "follow_button": ["follow", "com.zhiliaoapp.musically:id/btn_follow"],
        "search_tab": ["search", "com.zhiliaoapp.musically:id/search"],
    },
    "facebook": {
        "like_button": ["like", "Like", "com.facebook.katana:id/reaction_button"],
        "story_bar": ["story", "com.facebook.katana:id/stories_tray"],
        "profile_link": ["com.facebook.katana:id/actor_name"],
    },
    "twitter": {
        "like_button": ["like", "heart", "com.twitter.android:id/like_button"],
        "retweet_button": ["retweet", "com.twitter.android:id/retweet"],
        "profile_link": ["com.twitter.android:id/tweet_author_name"],
    },
    "threads": {
        "like_button": ["like", "heart", "com.instagram.barcelona:id/like_button"],
        "profile_link": ["com.instagram.barcelona:id/username"],
    },
}

_cache: dict[str, tuple[dict, float]] = {}
CACHE_MAX_AGE = 86400


def _sh(serial: str, cmd: str, timeout: int = 10) -> str:
    try:
        return adb_cmd(serial, ["shell"] + cmd.split(), timeout=timeout).stdout.strip()
    except Exception:
        return ""


def _parse_bounds(bounds_str: str) -> dict | None:
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
    if not m:
        return None
    x1, y1, x2, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    return {
        "x": (x1 + x2) // 2,
        "y": (y1 + y2) // 2,
        "w": x2 - x1,
        "h": y2 - y1,
    }


def _search_xml(xml: str, hints: list[str]) -> dict | None:
    for node_match in re.finditer(r"<node\s([^>]+?)/?>", xml, re.DOTALL):
        attrs_str = node_match.group(1)
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', attrs_str))
        text_val = attrs.get("text", "").lower()
        rid = attrs.get("resource-id", "").lower()
        cdesc = attrs.get("content-desc", "").lower()
        bounds = attrs.get("bounds", "")
        for hint in hints:
            h = hint.lower()
            if h in text_val or h in rid or h in cdesc:
                result = _parse_bounds(bounds)
                if result:
                    result["text"] = attrs.get("text", "")
                    return result
    return None


def find_element(serial: str, hints: list[str]) -> dict | None:
    cache_key = f"{serial}:{','.join(hints)}"
    cached = _cache.get(cache_key)
    if cached and (time.time() - cached[1]) < CACHE_MAX_AGE:
        return cached[0]

    _sh(serial, "uiautomator dump /sdcard/u.xml")
    xml = _sh(serial, "cat /sdcard/u.xml")
    result = _search_xml(xml, hints)

    if result is None:
        result = find_element_ocr(serial, hints)

    if result is None:
        _sh(serial, f"input swipe 540 1600 540 1100 400")
        time.sleep(1)
        _sh(serial, "uiautomator dump /sdcard/u.xml")
        xml = _sh(serial, "cat /sdcard/u.xml")
        result = _search_xml(xml, hints)

    if result:
        _cache[cache_key] = (result, time.time())

    return result


def find_element_ocr(serial: str, hints: list[str]) -> dict | None:
    try:
        import cv2
        import numpy as np
        import pytesseract

        from utils.adb_utils import find_adb
        import subprocess as _sp, sys as _sys
        _kw = {}
        if _sys.platform == "win32":
            _kw["creationflags"] = _sp.CREATE_NO_WINDOW
        raw = _sp.run(
            [find_adb(), "-s", serial, "shell", "screencap", "-p"],
            capture_output=True, timeout=15, **_kw,
        ).stdout
        if not raw:
            return None
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
        for hint in hints:
            h = hint.lower()
            for i, word in enumerate(data["text"]):
                if data["conf"][i] > 40 and h in word.lower():
                    x = data["left"][i] + data["width"][i] // 2
                    y = data["top"][i] + data["height"][i] // 2
                    return {
                        "x": x, "y": y,
                        "w": data["width"][i], "h": data["height"][i],
                        "text": word,
                    }
    except Exception:
        pass
    return None
