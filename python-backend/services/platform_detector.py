"""Platform detection, launch, and screen-size helpers via ADB."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timezone

from utils.adb_utils import adb_cmd

logger = logging.getLogger(__name__)

KNOWN_PACKAGES: dict[str, str] = {
    "instagram": "com.instagram.android",
    "tiktok": "com.zhiliaoapp.musically",
    "facebook": "com.facebook.katana",
    "twitter": "com.twitter.android",
    "threads": "com.instagram.barcelona",
    "youtube": "com.google.android.youtube",
    "linkedin": "com.linkedin.android",
}

_PKG_TO_PLATFORM = {v: k for k, v in KNOWN_PACKAGES.items()}

PLATFORM_CAPABILITIES: dict[str, dict] = {
    "instagram": {
        "name": "Instagram",
        "package": "com.instagram.android",
        "supports_posting": True,
        "supports_stories": True,
        "supports_reels": True,
        "priority": 10,
    },
    "tiktok": {
        "name": "TikTok",
        "package": "com.zhiliaoapp.musically",
        "supports_posting": True,
        "supports_stories": False,
        "supports_reels": True,
        "priority": 9,
    },
    "threads": {
        "name": "Threads",
        "package": "com.instagram.barcelona",
        "supports_posting": True,
        "supports_stories": False,
        "supports_reels": False,
        "priority": 8,
    },
    "twitter": {
        "name": "Twitter/X",
        "package": "com.twitter.android",
        "supports_posting": True,
        "supports_stories": False,
        "supports_reels": False,
        "priority": 7,
    },
    "facebook": {
        "name": "Facebook",
        "package": "com.facebook.katana",
        "supports_posting": True,
        "supports_stories": True,
        "supports_reels": True,
        "priority": 6,
    },
    "youtube": {
        "name": "YouTube",
        "package": "com.google.android.youtube",
        "supports_posting": False,
        "supports_stories": False,
        "supports_reels": True,
        "priority": 5,
    },
    "linkedin": {
        "name": "LinkedIn",
        "package": "com.linkedin.android",
        "supports_posting": True,
        "supports_stories": False,
        "supports_reels": False,
        "priority": 4,
    },
}

_platform_cache: dict[str, tuple[float, list[dict]]] = {}
_CACHE_TTL = 300


def _sh(serial: str, cmd: str, timeout: int = 10) -> str:
    try:
        return adb_cmd(serial, ["shell"] + cmd.split(), timeout=timeout).stdout.strip()
    except Exception:
        return ""


def detect_platforms(serial: str) -> list[dict]:
    raw = _sh(serial, "pm list packages")
    installed_pkgs = {line.replace("package:", "").strip() for line in raw.splitlines()}
    results = []
    for key, info in PLATFORM_CAPABILITIES.items():
        pkg = info["package"]
        is_installed = pkg in installed_pkgs
        version = ""
        if is_installed:
            ver_info = _sh(serial, f"dumpsys package {pkg} | grep versionName")
            m = re.search(r"versionName=(\S+)", ver_info)
            if m:
                version = m.group(1)
        results.append({
            "platform": key,
            "name": info["name"],
            "package": pkg,
            "installed": is_installed,
            "version": version,
            "supports_posting": info["supports_posting"],
            "supports_stories": info["supports_stories"],
            "supports_reels": info["supports_reels"],
        })
    return results


async def detect_and_save_platforms(serial: str) -> list[dict]:
    """Detect installed platforms, persist to DB, return results."""
    from app.database import SessionLocal
    from app.models.platform import Platform
    from app.models._common import utc_now

    detected = detect_platforms(serial)
    now = utc_now()

    try:
        async with SessionLocal() as session:
            from sqlalchemy import select

            for d in detected:
                existing = (
                    await session.execute(
                        select(Platform).where(
                            Platform.device_serial == serial,
                            Platform.package_name == d["package"],
                        )
                    )
                ).scalar_one_or_none()

                if existing:
                    existing.is_installed = d["installed"]
                    existing.version = d.get("version", "")
                    existing.last_seen_at = now
                else:
                    info = PLATFORM_CAPABILITIES.get(d["platform"], {})
                    session.add(Platform(
                        device_serial=serial,
                        platform_name=d.get("name", d["platform"]),
                        package_name=d["package"],
                        version=d.get("version", ""),
                        is_installed=d["installed"],
                        is_supported=True,
                        supports_posting=info.get("supports_posting", True),
                        supports_stories=info.get("supports_stories", False),
                        supports_reels=info.get("supports_reels", False),
                        priority=info.get("priority", 5),
                        last_seen_at=now,
                    ))

            await session.commit()
    except Exception as e:
        logger.warning("Failed to persist platforms to DB: %s", e)

    installed_count = sum(1 for d in detected if d["installed"])
    logger.info("Detected %d platforms on %s", installed_count, serial)

    _platform_cache[serial] = (time.time(), detected)
    return detected


def get_cached_platforms(serial: str, force: bool = False) -> list[dict] | None:
    if force:
        return None
    entry = _platform_cache.get(serial)
    if entry and (time.time() - entry[0]) < _CACHE_TTL:
        return entry[1]
    return None


async def launch_platform(serial: str, package: str) -> bool:
    _sh(serial, f"monkey -p {package} -c android.intent.category.LAUNCHER 1")
    for _ in range(20):
        await asyncio.sleep(0.5)
        out = _sh(serial, "dumpsys window | grep mCurrentFocus")
        if package in out:
            return True
    return False


def get_screen_size(serial: str) -> tuple[int, int]:
    raw = _sh(serial, "wm size")
    m = re.search(r"(\d+)x(\d+)", raw)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 1080, 2400
