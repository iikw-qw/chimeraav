"""Request validators for device/platform checks."""
from __future__ import annotations

from fastapi import HTTPException


def validate_device_platform(
    serial: str | None,
    platform: str | None,
    platforms: list[str] | None = None,
) -> None:
    if not serial or serial.strip() == "":
        raise HTTPException(400, detail={
            "error": "no_device_selected",
            "message": "Select a device first",
            "instructions": [
                "Connect a device via USB or Wi-Fi",
                "Click on the device card to select it",
                "Ensure Chimera Agent is installed",
            ],
        })

    active_platforms = platforms or ([platform] if platform else [])
    if not active_platforms or all(not p for p in active_platforms):
        raise HTTPException(400, detail={
            "error": "no_platform_selected",
            "message": "Select at least one platform",
            "instructions": [
                "Choose a platform (Instagram, TikTok, etc.)",
                "Only installed platforms can be selected",
                "Check platform availability with the detect button",
            ],
        })


async def validate_platforms_exist(serial: str) -> list[dict]:
    """Check device has at least one installed platform via ADB scan."""
    from services.platform_detector import detect_platforms

    detected = detect_platforms(serial)
    installed = [d for d in detected if d.get("installed")]

    if not installed:
        raise HTTPException(400, detail={
            "error": "no_platforms_detected",
            "message": "No installed platforms detected",
            "instructions": [
                "Connect device via Chimera Agent (click 'Connect Device')",
                "Install social media apps: Instagram, TikTok, Threads",
                "Click 'Detect Platforms' to refresh",
                "Check that USB Debugging is enabled",
                "Try restarting Chimera Agent",
            ],
            "actions": [
                {"label": "Detect Again", "action": "detect_platforms"},
                {"label": "Connect Device", "action": "connect_device"},
            ],
        })

    return installed
