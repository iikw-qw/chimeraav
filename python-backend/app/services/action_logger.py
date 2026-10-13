"""Centralized action logger — writes to DB and broadcasts via WebSocket."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.api._hub import hub
from app.database import SessionLocal
from app.models.action_log import ActionLog

logger = logging.getLogger("chimera.action_logger")

ACTION_TYPES = frozenset({
    # Device management
    "device_loaded",
    "device_scan",
    "device_found",
    "device_connected",
    "device_launch",
    "device_launch_complete",
    "device_reboot_wait",
    "device_reboot_detected",
    "device_usb_found",
    "device_start_lock_wait",
    "device_start_lock_acquired",
    "device_pairing_failed",
    # Autostart
    "autostart_check",
    "autostart_begin",
    "autostart_device",
    "autostart_complete",
    # Cleanup
    "cleanup_start",
    "cleanup_kill_processes",
    "cleanup_ports",
    "cleanup_forwards",
    "cleanup_complete",
    # Tunnel
    "tunnel_start",
    "tunnel_check",
    "tunnel_attempt",
    "tunnel_running",
    "tunnel_failed",
    "tunnel_existing",
    # WDA
    "wda_start",
    "wda_running",
    "wda_failed",
    "wda_recovery",
    "wda_recovery_complete",
    "wda_recovery_failed",
    "wda_log_received",
    "wda_crash",
    "wda_connection_refused",
    "wda_connection_reset",
    # Port forwarding
    "port_forward_start",
    "port_forward_running",
    "port_forward_cleanup",
    "port_cleanup",
    # Developer image
    "image_mount",
    "image_mount_ok",
    # Supervised pairing
    "supervised_pair",
    "supervised_pair_ok",
    "supervised_pair_force",
    # Device lifecycle
    "restart_start",
    "restart_cleanup",
    "restart_recovery_lock",
    "restart_fallback",
    "restart_error",
    "restart_complete",
    "stop_device",
    "stop_tunnel",
    "stop_wda",
    "stop_forward",
    "stop_complete",
    # Alert watcher
    "alert_watcher_enabled",
    "alert_watcher_dismissed",
    "alert_watcher_allow_access",
    # OCR
    "ocr_load",
    "ocr_ready",
    "ocr_text_found",
    # UI interactions
    "ui_tap",
    "ui_search_button",
    "ui_search_field",
    "ui_input_text",
    "ui_scroll_down",
    "ui_find_button",
    # Settings
    "settings_open",
    "settings_search",
    "settings_general",
    "settings_session_error",
    "settings_launch_failed",
    # Telegram
    "telegram_send",
    "telegram_sent",
    # Runtime
    "runtime_flags",
    "watcher_popup_config",
})


async def log_action(
    action_type: str,
    *,
    device_id: str | None = None,
    level: str = "info",
    details: dict[str, Any] | None = None,
    broadcast: bool = True,
) -> ActionLog | None:
    try:
        async with SessionLocal() as session:
            entry = ActionLog(
                device_id=device_id,
                level=level,
                action_type=action_type,
                details=details,
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)

        if broadcast:
            await hub.broadcast("logs", {
                "id": entry.id,
                "created_at": entry.created_at.isoformat() if entry.created_at else datetime.now(timezone.utc).isoformat(),
                "level": entry.level,
                "device_id": entry.device_id,
                "action_type": entry.action_type,
                "details": entry.details,
            })

        return entry
    except Exception as exc:
        logger.error("Failed to log action %s: %s", action_type, exc)
        return None


async def log_info(action_type: str, device_id: str | None = None, **details: Any) -> ActionLog | None:
    return await log_action(action_type, device_id=device_id, level="info", details=details or None)


async def log_warning(action_type: str, device_id: str | None = None, **details: Any) -> ActionLog | None:
    return await log_action(action_type, device_id=device_id, level="warning", details=details or None)


async def log_error(action_type: str, device_id: str | None = None, **details: Any) -> ActionLog | None:
    return await log_action(action_type, device_id=device_id, level="error", details=details or None)
