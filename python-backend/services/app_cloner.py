"""App cloning detection and multi-account support."""
from __future__ import annotations

import re

from utils.adb_utils import adb_command, adb_shell
from utils.logger import get_logger

logger = get_logger(__name__)

CLONE_SETTINGS = {
    "samsung":  {"setting": "dual_messenger_enabled", "method": "dual_messenger"},
    "xiaomi":   {"setting": "dual_app_enabled", "method": "dual_apps"},
    "oneplus":  {"setting": "parallel_apps", "method": "parallel_apps"},
    "huawei":   {"setting": "app_twin", "method": "app_twin"},
    "oppo":     {"setting": "clone_apps", "method": "clone_apps"},
    "realme":   {"setting": "clone_apps", "method": "clone_apps"},
    "vivo":     {"setting": "app_clone", "method": "app_clone"},
}


async def detect_device_brand(serial: str) -> str:
    brand = await adb_shell(serial, "getprop ro.product.brand")
    return brand.lower().strip()


async def check_clone_support(serial: str) -> dict:
    """Check if device supports built-in app cloning."""
    brand = await detect_device_brand(serial)

    has_builtin = brand in CLONE_SETTINGS
    method = CLONE_SETTINGS.get(brand, {}).get("method", "none")

    cloner_apps = {
        "app_cloner": "com.applisto.appcloner",
        "parallel_space": "com.lbe.parallel.intl",
        "dual_space": "com.ludashi.dualspace",
        "island": "com.oasisfeng.island",
    }

    installed_cloners: list[str] = []
    packages = await adb_shell(serial, "pm list packages")
    for name, pkg in cloner_apps.items():
        if pkg in packages:
            installed_cloners.append(name)

    return {
        "brand": brand,
        "has_builtin_clone": has_builtin,
        "builtin_method": method,
        "installed_cloners": installed_cloners,
        "can_clone": has_builtin or len(installed_cloners) > 0,
    }


async def detect_cloned_apps(serial: str) -> list[dict]:
    """Detect already cloned social apps on device."""
    clones: list[dict] = []
    packages = await adb_shell(serial, "pm list packages")

    CLONE_PATTERNS: dict[str, list[str]] = {
        "instagram": [
            "com.instagram.android.clone",
            "com.instagram.android_clone",
            "com.instagram.android.1",
            "com.instagram.android_1",
        ],
        "tiktok": [
            "com.zhiliaoapp.musically.clone",
            "com.zhiliaoapp.musically_clone",
            "com.zhiliaoapp.musically.1",
        ],
        "facebook": [
            "com.facebook.katana.clone",
            "com.facebook.katana_clone",
        ],
        "twitter": [
            "com.twitter.android.clone",
            "com.twitter.android_clone",
        ],
    }

    users = await adb_shell(serial, "pm list users")
    user_ids = re.findall(r"UserInfo\{(\d+):", users)

    for uid in user_ids:
        if uid == "0":
            continue
        user_packages = await adb_shell(serial, f"pm list packages --user {uid}")
        for platform, pkg in [
            ("instagram", "com.instagram.android"),
            ("tiktok", "com.zhiliaoapp.musically"),
            ("threads", "com.instagram.barcelona"),
        ]:
            if pkg in user_packages:
                clones.append({
                    "platform": platform,
                    "package": pkg,
                    "user_id": int(uid),
                    "method": "dual_profile",
                })

    for platform, patterns in CLONE_PATTERNS.items():
        for pattern in patterns:
            if pattern in packages:
                clones.append({
                    "platform": platform,
                    "package": pattern,
                    "user_id": 0,
                    "method": "cloned_package",
                })

    return clones


async def enable_dual_messenger(serial: str, package: str) -> dict:
    """Try to enable built-in dual messenger for a package."""
    brand = await detect_device_brand(serial)

    if brand == "samsung":
        await adb_shell(
            serial,
            f"am start -a com.samsung.android.action.DUAL_MESSENGER "
            f"-e package_name {package}",
        )
        return {
            "status": "opened_settings", "brand": brand,
            "message": "Samsung Dual Messenger settings opened. Enable the toggle for this app.",
        }

    elif brand == "xiaomi":
        await adb_shell(
            serial,
            "am start -a android.settings.APPLICATION_DEVELOPMENT_SETTINGS",
        )
        return {
            "status": "opened_settings", "brand": brand,
            "message": "Open Xiaomi Settings → Dual Apps and enable this app.",
        }

    else:
        await adb_shell(serial, "am start -a android.settings.APPLICATION_SETTINGS")
        return {
            "status": "opened_settings", "brand": brand,
            "message": f"Look for Clone/Dual/Parallel Apps in Settings for {brand}.",
        }


async def launch_cloned_app(serial: str, package: str, user_id: int = 0) -> bool:
    """Launch a cloned app in the correct user profile."""
    if user_id > 0:
        result = await adb_command(
            serial,
            ["shell", "am", "start", "--user", str(user_id),
             "-n", f"{package}/.MainActivity"],
        )
    else:
        result = await adb_command(
            serial,
            ["shell", "monkey", "-p", package,
             "-c", "android.intent.category.LAUNCHER", "1"],
        )
    return result.returncode == 0
