"""Warmup full — platform-aware warmup with session tracking, encounter
tracking, human cursor, UIFinder, multi-platform switching, blacklist/whitelist,
night mode, and WebSocket broadcast.
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from datetime import datetime, timezone

from utils.adb_utils import adb_cmd

from services.human_cursor import (
    human_tap, human_swipe, chaotic_swipe, human_type,
    human_tap_advanced, human_swipe_bezier,
)
from services.platform_detector import KNOWN_PACKAGES, get_screen_size, launch_platform
from services.timing_engine import get_timing, get_probability, thinking_pause, human_delay
from services.ui_finder import BUTTON_MAP, find_element

logger = logging.getLogger(__name__)

ACTION_WEIGHTS = {
    "scroll_feed": 28,
    "like_post": 18,
    "visit_profile": 12,
    "deep_profile": 8,
    "view_story": 10,
    "search": 5,
    "chaotic_swipe": 7,
    "dm_scan": 4,
    "pause": 8,
}

NIGHT_MODE_WEIGHTS = {
    "scroll_feed": 50,
    "like_post": 30,
    "pause": 20,
}

ACTION_LABELS = {
    "scroll_feed": "Scrolling feed...",
    "like_post": "Liking post...",
    "visit_profile": "Visiting profile...",
    "deep_profile": "Deep profile visit...",
    "view_story": "Watching story...",
    "search": "Searching...",
    "chaotic_swipe": "Chaotic swipe...",
    "dm_scan": "Scanning DMs...",
    "pause": "Taking a break...",
}

SEARCH_WORDS = [
    "travel", "food", "fitness", "music", "art", "nature",
    "tech", "fashion", "sports", "cars", "beauty", "gaming",
    "photography", "design", "funny", "cats", "dogs", "sunset",
    "coffee", "architecture", "vintage", "minimal", "plants",
    "ocean", "mountains", "city", "night", "colorful", "rain",
    "space", "books", "cooking", "hiking", "surfing", "yoga",
]

STORY_REPLIES = [
    "fire", "nice!", "love this", "amazing", "wow",
    "love it", "so cool", "incredible", "yes!",
]

WARMUP_MODE_SINGLE = "single"
WARMUP_MODE_SEQUENTIAL = "sequential"
WARMUP_MODE_RANDOM_SWITCH = "random_switch"

_stop_flags: dict[str, bool] = {}
_active_warmups: dict[str, bool] = {}
_paused_warmups: dict[str, bool] = {}
_sessions: dict[str, dict] = {}
_encounters: dict[str, dict] = {}
_blacklist: list[dict] = []
_whitelist: list[dict] = []
_presets: list[dict] = []


def stop_requested(serial: str) -> bool:
    return _stop_flags.get(serial, False)


def request_stop(serial: str) -> None:
    _stop_flags[serial] = True
    _active_warmups[serial] = False


def clear_stop(serial: str) -> None:
    _stop_flags.pop(serial, None)


def is_warmup_active(serial: str) -> bool:
    return _active_warmups.get(serial, False)


async def pause_warmup(serial: str) -> None:
    _paused_warmups[serial] = True


async def unpause_warmup(serial: str) -> None:
    _paused_warmups[serial] = False


def is_warmup_paused(serial: str) -> bool:
    return _paused_warmups.get(serial, False)


def _weighted_choice(weights: dict[str, int]) -> str:
    actions = list(weights.keys())
    w = list(weights.values())
    return random.choices(actions, weights=w, k=1)[0]


def _sh(serial: str, cmd: str) -> str:
    try:
        return adb_cmd(serial, ["shell"] + cmd.split(), timeout=10).stdout.strip()
    except Exception:
        return ""


def _extract_visible_username(serial: str) -> str:
    _sh(serial, "uiautomator dump /sdcard/u.xml")
    xml = _sh(serial, "cat /sdcard/u.xml")
    names = re.findall(r'text="(@[^"]+|[a-zA-Z0-9_.]{3,30})"', xml)
    return names[0] if names else "unknown"


def _increment_encounter(serial: str, account_id: str, platform: str) -> None:
    key = f"{serial}:{account_id}:{platform}"
    if key not in _encounters:
        _encounters[key] = {"count": 0, "last_story_reply": 0}
    _encounters[key]["count"] += 1


def _should_reply_to_story(serial: str, account_id: str, platform: str) -> bool:
    key = f"{serial}:{account_id}:{platform}"
    enc = _encounters.get(key)
    if not enc:
        return False
    if enc["count"] % 6 != 0:
        return False
    if enc["last_story_reply"] and (time.time() - enc["last_story_reply"]) < 86400:
        return False
    return True


def _mark_story_replied(serial: str, account_id: str, platform: str) -> None:
    key = f"{serial}:{account_id}:{platform}"
    if key in _encounters:
        _encounters[key]["last_story_reply"] = time.time()


# ── Blacklist / Whitelist ──────────────────────────────────

def is_blacklisted(username: str, platform: str) -> bool:
    return any(
        b["username"].lower() == username.lower() and b["platform"] == platform
        for b in _blacklist
    )


def is_whitelisted(username: str, platform: str) -> bool:
    return any(
        w["username"].lower() == username.lower() and w["platform"] == platform
        for w in _whitelist
    )


def add_to_blacklist(username: str, platform: str, reason: str = "") -> dict:
    if not is_blacklisted(username, platform):
        entry = {"username": username, "platform": platform, "reason": reason,
                 "added_at": datetime.now(timezone.utc).isoformat()}
        _blacklist.append(entry)
    return {"ok": True}


def remove_from_blacklist(username: str, platform: str) -> dict:
    _blacklist[:] = [b for b in _blacklist if not (
        b["username"].lower() == username.lower() and b["platform"] == platform
    )]
    return {"ok": True}


def get_blacklist() -> list[dict]:
    return _blacklist


def add_to_whitelist(username: str, platform: str, boost_factor: float = 2.0) -> dict:
    if not is_whitelisted(username, platform):
        entry = {"username": username, "platform": platform, "boost_factor": boost_factor,
                 "added_at": datetime.now(timezone.utc).isoformat()}
        _whitelist.append(entry)
    return {"ok": True}


def remove_from_whitelist(username: str, platform: str) -> dict:
    _whitelist[:] = [w for w in _whitelist if not (
        w["username"].lower() == username.lower() and w["platform"] == platform
    )]
    return {"ok": True}


def get_whitelist() -> list[dict]:
    return _whitelist


# ── Presets ────────────────────────────────────────────────

def save_preset(name: str, weights: dict, platforms: list[str],
                mode: str = "single", intensity: int = 5, night_mode: bool = False) -> dict:
    existing = next((p for p in _presets if p["name"] == name), None)
    data = {
        "name": name, "weights": weights, "platforms": platforms,
        "mode": mode, "intensity": intensity, "night_mode": night_mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if existing:
        existing.update(data)
    else:
        data["id"] = len(_presets) + 1
        _presets.append(data)
    return {"ok": True, "preset": data}


def get_presets() -> list[dict]:
    return _presets


def get_preset(preset_id: int) -> dict | None:
    return next((p for p in _presets if p.get("id") == preset_id), None)


def delete_preset(preset_id: int) -> dict:
    _presets[:] = [p for p in _presets if p.get("id") != preset_id]
    return {"ok": True}


# ── WarmupFull class ───────────────────────────────────────

class WarmupFull:
    def __init__(self, serial: str, platform: str, account_username: str | None = None,
                 account_user_id: int = 0) -> None:
        self.serial = serial
        self.platform = platform
        self.account = account_username
        self.account_user_id = account_user_id
        self.pkg = KNOWN_PACKAGES.get(platform, KNOWN_PACKAGES["instagram"])
        self.screen_w, self.screen_h = 1080, 2400
        self.x_zones = [int(f * 1080) for f in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)]
        self.y_zones = [int(f * 2400) for f in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)]
        self._btn_map = BUTTON_MAP.get(platform, BUTTON_MAP.get("instagram", {}))

    def _find(self, element_key: str) -> dict | None:
        hints = self._btn_map.get(element_key, [])
        if not hints:
            return None
        return find_element(self.serial, hints)

    async def _tap(self, x: float, y: float, w: float = 60, h: float = 60) -> None:
        await human_tap(self.serial, x, y, w, h, self.screen_w, self.screen_h)

    async def _swipe(self, direction: str = "up") -> None:
        await human_swipe(self.serial, direction, self.screen_w, self.screen_h)

    async def _broadcast(self, action: str, stats: dict, elapsed: int,
                         detail: str = "", action_count: int = 0,
                         debug_data: dict | None = None) -> None:
        try:
            from utils.ws_manager import ws_manager
            payload: dict = {
                "action": action,
                "platform": self.platform,
                "total_scrolls": stats.get("scrolls", 0),
                "total_likes": stats.get("likes", 0),
                "total_profiles": stats.get("profiles", 0),
                "total_stories": stats.get("stories", 0),
                "total_dms": stats.get("dms", 0),
                "elapsed_seconds": elapsed,
                "current_action_label": ACTION_LABELS.get(action, action),
                "action_count": action_count,
                "log_entry": {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "action": action,
                    "detail": detail or ACTION_LABELS.get(action, action),
                },
            }
            if debug_data:
                payload["debug"] = debug_data
            await ws_manager.broadcast(f"warmup_{self.serial}", payload)
        except Exception:
            pass

    def _update_platform(self, platform: str) -> None:
        self.platform = platform
        self.pkg = KNOWN_PACKAGES.get(platform, KNOWN_PACKAGES["instagram"])
        self._btn_map = BUTTON_MAP.get(platform, BUTTON_MAP.get("instagram", {}))

    # ── Actions ─────────────────────────────────────────────────

    async def _scroll_feed(self, stats: dict) -> None:
        count = random.randint(2, 5)
        for _ in range(count):
            await human_swipe_bezier(self.serial, "up")
            stats["scrolls"] += 1
            if random.random() < 0.3:
                await asyncio.sleep(get_timing(self.platform, "feed_scroll_pause"))
            else:
                await asyncio.sleep(max(0.5, random.gauss(1.2, 0.4)))
            if random.random() < 0.08:
                await self._swipe("down")
                await asyncio.sleep(random.uniform(1, 3))

    async def _like_post(self, stats: dict) -> None:
        btn = self._find("like_button")
        if random.random() < 0.3 or not btn:
            post_x = self.screen_w * random.uniform(0.3, 0.7)
            post_y = self.screen_h * random.uniform(0.35, 0.55)
            await human_tap_advanced(self.serial, post_x, post_y, 40, 40, tap_type="quick")
            await asyncio.sleep(random.uniform(0.1, 0.18))
            await human_tap_advanced(self.serial, post_x + random.gauss(0, 3), post_y + random.gauss(0, 3), 40, 40, tap_type="quick")
        elif btn:
            await human_tap_advanced(self.serial, btn["x"], btn["y"], btn.get("w", 40), btn.get("h", 40), tap_type="quick")
        stats["likes"] += 1

        if get_probability(self.platform, "save_probability"):
            save_hints = self._btn_map.get("save_button", ["save", "bookmark"])
            save_btn = find_element(self.serial, save_hints) if save_hints else None
            if save_btn:
                await self._tap(save_btn["x"], save_btn["y"], save_btn.get("w", 40), save_btn.get("h", 40))

    async def _visit_profile(self, stats: dict) -> None:
        btn = self._find("profile_link")
        if not btn:
            return
        account_id = _extract_visible_username(self.serial)
        if is_blacklisted(account_id, self.platform):
            logger.info("Skipping blacklisted %s", account_id)
            return
        if is_whitelisted(account_id, self.platform):
            await self._deep_profile(stats)
            return
        await human_tap_advanced(self.serial, btn["x"], btn["y"], btn.get("w", 50), btn.get("h", 50), tap_type="normal")
        await asyncio.sleep(get_timing(self.platform, "profile_browse_time") * 0.3)
        stats["profiles"] += 1
        _increment_encounter(self.serial, account_id, self.platform)
        _sh(self.serial, "input keyevent KEYCODE_BACK")
        await asyncio.sleep(random.uniform(0.8, 1.5))

    async def _deep_profile(self, stats: dict) -> None:
        btn = self._find("profile_link")
        if not btn:
            return
        await self._tap(btn["x"], btn["y"], btn.get("w", 50), btn.get("h", 50))
        await asyncio.sleep(random.uniform(1, 3))
        await asyncio.sleep(random.uniform(1.5, 4))

        for _ in range(random.randint(3, 8)):
            await self._swipe("up")
            await asyncio.sleep(random.uniform(1.5, 4))

        for _ in range(random.randint(1, 2)):
            post_x = random.choice(self.x_zones[1:4])
            post_y = random.choice(self.y_zones[3:7])
            await self._tap(post_x, post_y, 100, 100)
            await asyncio.sleep(random.uniform(3, 7))
            _sh(self.serial, "input keyevent KEYCODE_BACK")
            await asyncio.sleep(random.uniform(0.8, 1.5))

        if random.random() < 0.20:
            follow_btn = self._find("follow_button")
            if follow_btn:
                await self._tap(follow_btn["x"], follow_btn["y"],
                                follow_btn.get("w", 40), follow_btn.get("h", 40))

        if random.random() < 0.10:
            msg_btn = find_element(self.serial, ["message", "Message"])
            if msg_btn:
                await self._tap(msg_btn["x"], msg_btn["y"],
                                msg_btn.get("w", 40), msg_btn.get("h", 40))
                await asyncio.sleep(random.uniform(1, 2))
                _sh(self.serial, "input keyevent KEYCODE_BACK")

        stats["profiles"] += 1
        _sh(self.serial, "input keyevent KEYCODE_BACK")
        await asyncio.sleep(random.uniform(0.8, 1.5))

    async def _view_story(self, stats: dict) -> None:
        btn = self._find("story_ring")
        if not btn:
            return
        await human_tap_advanced(self.serial, btn["x"], btn["y"], btn.get("w", 60), btn.get("h", 60), tap_type="quick")

        for _ in range(random.randint(2, 5)):
            account_id = _extract_visible_username(self.serial)
            if _should_reply_to_story(self.serial, account_id, self.platform):
                await asyncio.sleep(get_timing(self.platform, "story_view_time"))
                reply_btn = self._find("reply_field")
                if reply_btn:
                    await self._tap(reply_btn["x"], reply_btn["y"],
                                    reply_btn.get("w", 200), reply_btn.get("h", 50))
                    await asyncio.sleep(random.uniform(1, 2))
                    await human_type(self.serial, random.choice(STORY_REPLIES))
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    send_btn = find_element(self.serial, ["send", "Send"])
                    if send_btn:
                        await self._tap(send_btn["x"], send_btn["y"],
                                        send_btn.get("w", 40), send_btn.get("h", 40))
                    else:
                        _sh(self.serial, "input keyevent KEYCODE_ENTER")
                _mark_story_replied(self.serial, account_id, self.platform)
            else:
                await asyncio.sleep(get_timing(self.platform, "story_view_time"))

            if random.random() < 0.15:
                await asyncio.sleep(random.uniform(0.5, 1.5))

            if random.random() < 0.05:
                await human_swipe_bezier(self.serial, "right")
                await asyncio.sleep(random.uniform(2, 4))

            await human_swipe_bezier(self.serial, "left")
            await asyncio.sleep(random.uniform(0.3, 0.8))
            stats["stories"] += 1

        _sh(self.serial, "input keyevent KEYCODE_BACK")
        await asyncio.sleep(random.uniform(0.5, 1.0))

    async def _search_action(self, stats: dict) -> None:
        word = random.choice(SEARCH_WORDS)[:random.randint(2, 5)]

        search_btn = self._find("search_tab")
        if not search_btn:
            return
        await self._tap(search_btn["x"], search_btn["y"],
                        search_btn.get("w", 40), search_btn.get("h", 40))
        await asyncio.sleep(random.uniform(0.8, 1.5))

        input_field = find_element(self.serial, ["search", "Search...", "search_edittext"])
        if not input_field:
            _sh(self.serial, "input keyevent KEYCODE_BACK")
            return
        await self._tap(input_field["x"], input_field["y"],
                        input_field.get("w", 40), input_field.get("h", 40))
        await asyncio.sleep(random.uniform(0.5, 1.0))
        await human_type(self.serial, word)
        await asyncio.sleep(random.uniform(1, 2))

        for _ in range(random.randint(2, 4)):
            await self._swipe("up")
            await asyncio.sleep(max(0.5, random.gauss(1.5, 0.5)))

        if random.random() < 0.15:
            await self._tap(
                random.uniform(0.2, 0.8) * self.screen_w,
                random.uniform(0.3, 0.6) * self.screen_h,
                100, 80,
            )
            await asyncio.sleep(random.uniform(2, 5))
            _sh(self.serial, "input keyevent KEYCODE_BACK")

        _sh(self.serial, "input keyevent KEYCODE_BACK")
        await asyncio.sleep(random.uniform(0.3, 0.8))
        _sh(self.serial, "input keyevent KEYCODE_BACK")

    async def _dm_scan(self, stats: dict) -> None:
        dm_hints = {
            "instagram": ["direct", "DM", "messages icon"],
            "tiktok": ["inbox", "messages"],
            "facebook": ["messenger", "chat"],
            "twitter": ["messages", "DM", "envelope"],
            "threads": ["activity", "messages"],
        }
        hints = dm_hints.get(self.platform, ["messages"])
        btn = find_element(self.serial, hints)
        if not btn:
            return
        await self._tap(btn["x"], btn["y"], btn.get("w", 40), btn.get("h", 40))
        await asyncio.sleep(random.uniform(2, 4))
        for _ in range(random.randint(1, 3)):
            await self._swipe("up")
            await asyncio.sleep(random.uniform(1, 2))
        _sh(self.serial, "input keyevent KEYCODE_BACK")
        await asyncio.sleep(random.uniform(0.5, 1.0))
        stats["dms"] += 1

    # ── Additional random actions (Block 21) ───────────────────

    async def _maybe_unlike(self, stats: dict) -> None:
        if random.random() > 0.05:
            return
        await asyncio.sleep(random.uniform(30, 90))
        btn = self._find("like_button")
        if btn:
            await self._tap(btn["x"], btn["y"], btn.get("w", 40), btn.get("h", 40))
            stats["likes"] = max(0, stats["likes"] - 1)

    async def _maybe_save_post(self) -> None:
        if random.random() > 0.10:
            return
        hints = self._btn_map.get("save_button", ["save", "bookmark"])
        btn = find_element(self.serial, hints) if hints else None
        if btn:
            await self._tap(btn["x"], btn["y"], btn.get("w", 40), btn.get("h", 40))
            await asyncio.sleep(random.uniform(0.5, 1.5))

    async def _maybe_browse_comments(self) -> None:
        if random.random() > 0.35:
            return
        hints = self._btn_map.get("comment_icon", ["comment"])
        btn = find_element(self.serial, hints) if hints else None
        if not btn:
            return
        await self._tap(btn["x"], btn["y"], btn.get("w", 40), btn.get("h", 40))
        await asyncio.sleep(random.uniform(1, 2))
        for _ in range(random.randint(2, 5)):
            await human_swipe(self.serial, "up", self.screen_w, self.screen_h)
            await asyncio.sleep(random.uniform(1, 3))
        _sh(self.serial, "input keyevent KEYCODE_BACK")
        await asyncio.sleep(random.uniform(0.5, 1.0))

    async def _maybe_switch_tab(self) -> None:
        if random.random() > 0.20:
            return
        tabs = ["reels_tab", "search_tab"]
        tab_key = random.choice(tabs)
        hints = self._btn_map.get(tab_key)
        if not hints:
            return
        btn = find_element(self.serial, hints)
        if not btn:
            return
        await self._tap(btn["x"], btn["y"], btn.get("w", 40), btn.get("h", 40))
        await asyncio.sleep(random.uniform(2, 5))
        for _ in range(random.randint(1, 3)):
            await self._swipe("up")
            await asyncio.sleep(random.uniform(1, 3))
        _sh(self.serial, "input keyevent KEYCODE_BACK")
        await asyncio.sleep(random.uniform(0.5, 1.0))

    async def _maybe_open_share(self) -> None:
        if random.random() > 0.03:
            return
        hints = self._btn_map.get("share_button", ["share"])
        btn = find_element(self.serial, hints) if hints else None
        if btn:
            await self._tap(btn["x"], btn["y"], btn.get("w", 40), btn.get("h", 40))
            await asyncio.sleep(random.uniform(2, 4))
            _sh(self.serial, "input keyevent KEYCODE_BACK")

    async def _maybe_scroll_back(self) -> None:
        if random.random() > 0.08:
            return
        for _ in range(random.randint(1, 2)):
            await self._swipe("down")
            await asyncio.sleep(random.uniform(1, 3))

    async def _maybe_browse_reels(self) -> None:
        if random.random() > 0.20:
            return
        reels_hints = self._btn_map.get("reels_tab")
        if not reels_hints:
            return
        btn = find_element(self.serial, reels_hints)
        if not btn:
            return
        await self._tap(btn["x"], btn["y"], btn.get("w", 40), btn.get("h", 40))
        await asyncio.sleep(random.uniform(1.5, 3))

        for _ in range(random.randint(2, 5)):
            await asyncio.sleep(random.uniform(4, 15))
            if random.random() < 0.30:
                px = self.screen_w * 0.5
                py = self.screen_h * 0.5
                await self._tap(px, py, 80, 80)
                await asyncio.sleep(random.uniform(0.1, 0.18))
                await self._tap(px + random.gauss(0, 3), py + random.gauss(0, 3), 80, 80)
            await self._swipe("up")
            await asyncio.sleep(random.uniform(0.3, 0.8))

        _sh(self.serial, "input keyevent KEYCODE_BACK")

    # ── Platform switching ─────────────────────────────────────

    async def _switch_platform(self, new_platform: str) -> None:
        _sh(self.serial, "input keyevent KEYCODE_HOME")
        await asyncio.sleep(random.uniform(1.5, 3.0))
        self._update_platform(new_platform)
        await launch_platform(self.serial, self.pkg)
        await asyncio.sleep(random.uniform(2, 4))
        logger.info("Switched to %s on %s", new_platform, self.serial)

    # ── Main loop ───────────────────────────────────────────────

    async def run(
        self,
        duration_sec: int | None = None,
        intensity: float = 5.0,
        platforms: list[str] | None = None,
        mode: str = WARMUP_MODE_SINGLE,
        custom_weights: dict | None = None,
        custom_weights_per_platform: dict[str, dict] | None = None,
        night_mode: bool = False,
        debug: bool = False,
    ) -> dict:
        self.screen_w, self.screen_h = get_screen_size(self.serial)
        self.x_zones = [int(f * self.screen_w) for f in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)]
        self.y_zones = [int(f * self.screen_h) for f in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)]

        all_platforms = platforms or [self.platform]

        if night_mode:
            weights = NIGHT_MODE_WEIGHTS.copy()
        elif custom_weights:
            weights = custom_weights
        else:
            weights = ACTION_WEIGHTS.copy()

        if mode == WARMUP_MODE_SEQUENTIAL and len(all_platforms) > 1:
            per_platform_minutes = 10 + (int(intensity) * 2)
            total_minutes = per_platform_minutes * len(all_platforms)
        else:
            total_minutes = 10 + (int(intensity) * 3)

        if duration_sec is None:
            duration_sec = total_minutes * 60
        end_time = time.time() + duration_sec

        clear_stop(self.serial)
        _active_warmups[self.serial] = True
        if self.account_user_id > 0:
            from services.app_cloner import launch_cloned_app
            await launch_cloned_app(self.serial, self.pkg, self.account_user_id)
        else:
            await launch_platform(self.serial, self.pkg)
        await asyncio.sleep(random.uniform(3, 6))

        stats = {"scrolls": 0, "likes": 0, "profiles": 0, "stories": 0, "dms": 0, "time": 0}
        start = time.time()
        chaotic_counter = 0
        last_platform_switch = start
        platform_switch_interval = duration_sec / max(len(all_platforms), 1)
        min_platform_stay = 180

        _sessions[self.serial] = {
            "platform": self.platform,
            "account": self.account,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "stats": stats,
        }

        action_counter = 0

        while time.time() < end_time and not stop_requested(self.serial):
            while _paused_warmups.get(self.serial, False):
                await asyncio.sleep(0.5)

            # Platform switching
            if mode == WARMUP_MODE_RANDOM_SWITCH and len(all_platforms) > 1:
                if (random.random() < 0.02
                        and (time.time() - last_platform_switch) >= min_platform_stay):
                    new_platform = random.choice([p for p in all_platforms if p != self.platform])
                    await self._switch_platform(new_platform)
                    last_platform_switch = time.time()

            elif mode == WARMUP_MODE_SEQUENTIAL and len(all_platforms) > 1:
                elapsed_since_switch = time.time() - last_platform_switch
                if elapsed_since_switch >= platform_switch_interval:
                    current_idx = all_platforms.index(self.platform)
                    next_idx = (current_idx + 1) % len(all_platforms)
                    if next_idx != 0 or current_idx == len(all_platforms) - 1:
                        await self._switch_platform(all_platforms[next_idx])
                        last_platform_switch = time.time()

            if custom_weights_per_platform and self.platform in custom_weights_per_platform:
                current_weights = custom_weights_per_platform[self.platform]
            else:
                current_weights = weights

            action = _weighted_choice(current_weights)
            elapsed = int(time.time() - start)
            stats["time"] = elapsed
            action_counter += 1

            chaotic_counter += 1
            if chaotic_counter >= random.randint(8, 15):
                await chaotic_swipe(self.serial, self.screen_w, self.screen_h)
                chaotic_counter = 0

            try:
                if action == "scroll_feed":
                    await self._scroll_feed(stats)
                elif action == "like_post":
                    await self._like_post(stats)
                elif action == "visit_profile":
                    await self._visit_profile(stats)
                elif action == "deep_profile":
                    await self._deep_profile(stats)
                elif action == "view_story":
                    await self._view_story(stats)
                elif action == "search":
                    await self._search_action(stats)
                elif action == "chaotic_swipe":
                    await chaotic_swipe(self.serial, self.screen_w, self.screen_h)
                elif action == "dm_scan":
                    await self._dm_scan(stats)
                elif action == "pause":
                    pause_time = random.uniform(5, 20)
                    if night_mode:
                        pause_time = random.uniform(3, 10)
                    await asyncio.sleep(pause_time)
            except Exception as e:
                logger.error("Warmup action error: %s", e)

            if not night_mode:
                await self._maybe_unlike(stats)
                await self._maybe_save_post()
                await self._maybe_browse_comments()
                await self._maybe_switch_tab()
                await self._maybe_open_share()
                await self._maybe_scroll_back()
                await self._maybe_browse_reels()

            debug_payload = None
            if debug:
                debug_payload = {
                    "type": action,
                    "screen_w": self.screen_w,
                    "screen_h": self.screen_h,
                    "timestamp": time.time(),
                }
                if action in ("like_post", "visit_profile", "deep_profile"):
                    debug_payload["type"] = "tap"
                    debug_payload["x"] = int(self.screen_w * 0.5)
                    debug_payload["y"] = int(self.screen_h * 0.45)
                elif action in ("scroll_feed", "chaotic_swipe"):
                    debug_payload["type"] = "swipe"
                    debug_payload["direction"] = "up"
                    debug_payload["points"] = [
                        {"x": self.screen_w // 2, "y": int(self.screen_h * 0.7)},
                        {"x": self.screen_w // 2, "y": int(self.screen_h * 0.3)},
                    ]
                elif action == "view_story":
                    debug_payload["type"] = "swipe"
                    debug_payload["direction"] = "left"

            await self._broadcast(action, stats, elapsed,
                                  action_count=action_counter,
                                  debug_data=debug_payload)

            if night_mode:
                delay = random.uniform(3, 10)
            else:
                delay = human_delay(1.5)
            await asyncio.sleep(delay)

        session = _sessions.pop(self.serial, None)
        if session:
            session["ended_at"] = datetime.now(timezone.utc).isoformat()
            session["stats"] = stats

        clear_stop(self.serial)
        _active_warmups.pop(self.serial, None)
        _paused_warmups.pop(self.serial, None)
        return stats


def get_warmup_history(serial: str) -> list[dict]:
    return []


async def generate_warmup_report(session_id: int | str) -> dict:
    """Generate detailed report for a warmup session from in-memory data."""
    for serial, session in _sessions.items():
        if str(session.get("id", serial)) == str(session_id) or serial == str(session_id):
            stats = session.get("stats", {})
            started = session.get("started_at", "")
            ended = session.get("ended_at")
            duration = 0
            if started and ended:
                from datetime import datetime as dt
                try:
                    s = dt.fromisoformat(started)
                    e = dt.fromisoformat(ended)
                    duration = int((e - s).total_seconds())
                except Exception:
                    pass
            elif stats.get("time"):
                duration = stats["time"]

            total_actions = (stats.get("scrolls", 0) + stats.get("likes", 0) +
                             stats.get("profiles", 0) + stats.get("stories", 0) +
                             stats.get("dms", 0))
            apm = round(total_actions / max(duration / 60, 1), 1)

            enc_list = []
            for key, enc in _encounters.items():
                parts = key.split(":")
                if len(parts) >= 3 and parts[0] == serial:
                    enc_list.append({
                        "username": parts[1],
                        "count": enc.get("count", 0),
                    })
            enc_list.sort(key=lambda e: e["count"], reverse=True)

            return {
                "session_id": session_id,
                "serial": serial,
                "platform": session.get("platform", ""),
                "started_at": started,
                "ended_at": ended,
                "duration_seconds": duration,
                "duration_display": f"{duration // 60}m {duration % 60}s",
                "stats": {
                    "scrolls": stats.get("scrolls", 0),
                    "likes": stats.get("likes", 0),
                    "profiles": stats.get("profiles", 0),
                    "stories": stats.get("stories", 0),
                    "dms": stats.get("dms", 0),
                    "total_actions": total_actions,
                    "actions_per_minute": apm,
                },
                "encounters": {
                    "total": len(enc_list),
                    "accounts": enc_list[:20],
                },
            }

    return {"error": "Session not found"}
