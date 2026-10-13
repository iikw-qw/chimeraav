"""iOS device control via WebDriverAgent (WDA).

WDA is the de-facto layer Appium/Facebook use to script iOS UI. The user
either side-loads the official WDA build (no jailbreak — re-sign every 7 days)
or installs a persistent WDA.app via TrollStore / a jailbreak (covered by
Settings → Гайд → iOS-джейлбрейк).

Either way, the device exposes WDA's HTTP API on port 8100. iproxy/ttwiproxy
forward it to the host as 127.0.0.1:<wda_port>. We default to 8100; if the
user runs multiple devices each gets a different forwarded port and that
mapping is stored in app settings (`ios_wda_ports`, JSON dict udid→port).

This module is the thin wrapper:

    available()        — probe WDA reachability for a UDID
    open_app(bundle)   — launch by bundle id  (POST /session)
    tap(x, y)          — POST /session/<sid>/wda/tap/0
    swipe(x1,y1,x2,y2) — POST /session/<sid>/wda/dragfromtoforduration
    type_text(text)    — POST /session/<sid>/wda/keys
    screenshot()       — GET /session/<sid>/screenshot

If WDA isn't reachable we return None / False with a typed reason — never
crash. Callers surface the reason as an actionable toast.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger("chimera.ios_control")


_DEFAULT_WDA_PORT = 8100


@dataclass
class IOSResult:
    ok: bool
    detail: str
    session_id: str | None = None


# In-memory cache: udid → (port, session_id, last_seen)
_sessions: dict[str, tuple[int, str]] = {}


def _base_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


async def _wda_get(port: int, path: str, timeout: float = 6.0) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(f"{_base_url(port)}{path}")
            if r.status_code != 200:
                return None
            return r.json()
    except Exception as exc:
        logger.debug("wda GET %s failed: %s", path, exc)
        return None


async def _wda_post(
    port: int, path: str, payload: dict, timeout: float = 12.0
) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{_base_url(port)}{path}", json=payload)
            if r.status_code not in (200, 201):
                return None
            return r.json()
    except Exception as exc:
        logger.debug("wda POST %s failed: %s", path, exc)
        return None


async def available(port: int = _DEFAULT_WDA_PORT) -> bool:
    """Quick reachability probe — used by the UI to decide whether to show
    'iOS automation requires WDA' guidance."""
    info = await _wda_get(port, "/status", timeout=2.0)
    return info is not None


async def _ensure_session(udid: str, port: int, bundle_id: str | None) -> str | None:
    cached = _sessions.get(udid)
    if cached and cached[0] == port:
        return cached[1]
    payload: dict = {"capabilities": {"alwaysMatch": {}}}
    if bundle_id:
        payload["capabilities"]["alwaysMatch"]["bundleId"] = bundle_id
    resp = await _wda_post(port, "/session", payload, timeout=20.0)
    if resp is None:
        return None
    sid = resp.get("sessionId") or (resp.get("value") or {}).get("sessionId")
    if not sid:
        return None
    _sessions[udid] = (port, sid)
    return sid


async def open_app(udid: str, bundle_id: str, port: int = _DEFAULT_WDA_PORT) -> IOSResult:
    sid = await _ensure_session(udid, port, bundle_id)
    if sid is None:
        return IOSResult(False, "WDA не отвечает — проверьте, что WebDriverAgent установлен и iproxy запущен")
    return IOSResult(True, f"app {bundle_id} launched", sid)


async def tap(udid: str, x: int, y: int, port: int = _DEFAULT_WDA_PORT) -> IOSResult:
    sid = await _ensure_session(udid, port, None)
    if sid is None:
        return IOSResult(False, "WDA сессия не открыта")
    resp = await _wda_post(port, f"/session/{sid}/wda/tap/0", {"x": x, "y": y})
    if resp is None:
        return IOSResult(False, "tap отклонён WDA")
    return IOSResult(True, "tap ok", sid)


async def swipe(
    udid: str, x1: int, y1: int, x2: int, y2: int,
    duration_seconds: float = 0.4, port: int = _DEFAULT_WDA_PORT,
) -> IOSResult:
    sid = await _ensure_session(udid, port, None)
    if sid is None:
        return IOSResult(False, "WDA сессия не открыта")
    resp = await _wda_post(
        port,
        f"/session/{sid}/wda/dragfromtoforduration",
        {
            "fromX": x1, "fromY": y1, "toX": x2, "toY": y2,
            "duration": float(duration_seconds),
        },
    )
    if resp is None:
        return IOSResult(False, "swipe отклонён WDA")
    return IOSResult(True, "swipe ok", sid)


async def type_text(udid: str, text: str, port: int = _DEFAULT_WDA_PORT) -> IOSResult:
    sid = await _ensure_session(udid, port, None)
    if sid is None:
        return IOSResult(False, "WDA сессия не открыта")
    # WDA `keys` accepts a list of single-char strings.
    resp = await _wda_post(
        port, f"/session/{sid}/wda/keys", {"value": list(text)}, timeout=20.0,
    )
    if resp is None:
        return IOSResult(False, "type_text отклонён WDA")
    return IOSResult(True, "type ok", sid)


async def page_source(udid: str, port: int = _DEFAULT_WDA_PORT) -> str | None:
    """Return the current screen's accessibility-tree XML — iOS analogue of
    `uiautomator dump`. Used by auto-login to discover login fields."""
    sid = await _ensure_session(udid, port, None)
    if sid is None:
        return None
    resp = await _wda_get(port, f"/session/{sid}/source")
    if resp is None:
        return None
    val = resp.get("value")
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return json.dumps(val)
    return None


async def screenshot_b64(udid: str, port: int = _DEFAULT_WDA_PORT) -> str | None:
    sid = await _ensure_session(udid, port, None)
    if sid is None:
        return None
    resp = await _wda_get(port, f"/session/{sid}/screenshot", timeout=10.0)
    if resp is None:
        return None
    val = resp.get("value")
    return val if isinstance(val, str) else None


async def close_session(udid: str) -> None:
    cached = _sessions.pop(udid, None)
    if not cached:
        return
    port, sid = cached
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            await client.delete(f"{_base_url(port)}/session/{sid}")
    except Exception:
        pass


# Bundle IDs for the supported platforms (iOS App Store IDs).
IOS_BUNDLE_BY_PLATFORM: dict[str, str] = {
    "instagram": "com.burbn.instagram",
    "tiktok": "com.zhiliao.musically",
    "twitter": "com.atebits.Tweetie2",
    "x": "com.atebits.Tweetie2",
    "facebook": "com.facebook.Facebook",
    "youtube": "com.google.ios.youtube",
    "threads": "com.burbn.barcelona",
    "telegram": "ph.telegra.Telegraph",
    "reddit": "com.reddit.Reddit",
}
