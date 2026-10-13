"""iOS automation API — device management, WDA, tunnels, cleanup, alerts, OCR."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/ios", tags=["ios-automation"])


# ── Device Management ────────────────────────────────────────────

@router.post("/devices/scan")
async def scan_devices() -> dict[str, Any]:
    from app.services.ios_device_manager import ios_device_manager
    devices = await ios_device_manager.scan_devices()
    return {
        "ok": True,
        "count": len(devices),
        "devices": [{"udid": d.udid, "model": d.model, "name": d.name} for d in devices],
    }


@router.post("/devices/load")
async def load_devices(data: dict) -> dict[str, Any]:
    from app.services.ios_device_manager import ios_device_manager
    configs = data.get("devices", [])
    devices = await ios_device_manager.load_devices(configs)
    return {"ok": True, "count": len(devices)}


@router.post("/devices/autostart")
async def autostart_devices() -> dict[str, Any]:
    from app.services.ios_device_manager import ios_device_manager
    return await ios_device_manager.autostart_devices()


@router.post("/devices/{udid}/launch")
async def launch_device(udid: str, data: dict | None = None) -> dict[str, Any]:
    from app.services.ios_device_manager import ios_device_manager
    port = (data or {}).get("wda_port", 8100)
    ok = await ios_device_manager.launch_device(udid, port)
    return {"ok": ok, "udid": udid}


@router.post("/devices/{udid}/stop")
async def stop_device(udid: str) -> dict[str, Any]:
    from app.services.ios_device_manager import ios_device_manager
    await ios_device_manager.stop_device(udid)
    return {"ok": True, "udid": udid}


@router.post("/devices/{udid}/restart")
async def restart_device(udid: str) -> dict[str, Any]:
    from app.services.ios_device_manager import ios_device_manager
    ok = await ios_device_manager.restart_device(udid)
    return {"ok": ok, "udid": udid}


@router.post("/devices/{udid}/pair")
async def pair_device(udid: str, data: dict | None = None) -> dict[str, Any]:
    from app.services.ios_device_manager import ios_device_manager
    p12 = (data or {}).get("p12_file")
    password = (data or {}).get("password", "go-ios-auto")
    ok = await ios_device_manager.supervised_pair(udid, p12, password)
    return {"ok": ok, "udid": udid}


@router.post("/devices/{udid}/tunnel")
async def setup_tunnel(udid: str) -> dict[str, Any]:
    from app.services.ios_device_manager import ios_device_manager
    ok, pid = await ios_device_manager.setup_tunnel(udid)
    return {"ok": ok, "udid": udid, "pid": pid}


@router.post("/devices/{udid}/wda")
async def start_wda(udid: str, data: dict | None = None) -> dict[str, Any]:
    from app.services.ios_device_manager import ios_device_manager
    port = (data or {}).get("wda_port", 8100)
    ok, pid = await ios_device_manager.start_wda(udid, port)
    return {"ok": ok, "udid": udid, "pid": pid}


@router.post("/devices/{udid}/wda-recovery")
async def wda_recovery(udid: str, data: dict | None = None) -> dict[str, Any]:
    from app.services.ios_device_manager import ios_device_manager
    reason = (data or {}).get("reason", "connection_refused")
    ok = await ios_device_manager.wda_recovery(udid, reason)
    return {"ok": ok, "udid": udid}


# ── System Cleanup ───────────────────────────────────────────────

@router.post("/cleanup")
async def cleanup_system() -> dict[str, Any]:
    from app.services.system_cleanup import system_cleanup
    return await system_cleanup.full_cleanup()


@router.post("/cleanup/device/{udid}")
async def cleanup_device(udid: str, data: dict | None = None) -> dict[str, Any]:
    from app.services.system_cleanup import system_cleanup
    port = (data or {}).get("port", 8100)
    return await system_cleanup.cleanup_device(udid, port)


# ── Alert Watcher ────────────────────────────────────────────────

@router.post("/alert-watcher/enable")
async def enable_alert_watcher(data: dict) -> dict[str, Any]:
    from app.services.alert_watcher_service import alert_watcher
    device_name = data["device_name"]
    await alert_watcher.enable(device_name)
    return {"ok": True, "device": device_name}


@router.post("/alert-watcher/disable")
async def disable_alert_watcher(data: dict) -> dict[str, Any]:
    from app.services.alert_watcher_service import alert_watcher
    device_name = data["device_name"]
    await alert_watcher.disable(device_name)
    return {"ok": True, "device": device_name}


@router.post("/alert-watcher/start")
async def start_alert_watcher(data: dict) -> dict[str, Any]:
    from app.services.alert_watcher_service import alert_watcher
    device_name = data["device_name"]
    wda_port = data.get("wda_port", 8100)
    await alert_watcher.start_watching(device_name, wda_port)
    return {"ok": True, "device": device_name}


@router.post("/alert-watcher/dismiss")
async def dismiss_alerts(data: dict) -> dict[str, Any]:
    from app.services.alert_watcher_service import alert_watcher
    device_name = data["device_name"]
    wda_port = data.get("wda_port", 8100)
    dismissed = await alert_watcher.auto_dismiss_alerts(device_name, wda_port)
    return {"ok": dismissed, "device": device_name}


@router.get("/alert-watcher/status")
async def alert_watcher_status() -> dict[str, Any]:
    from app.services.alert_watcher_service import alert_watcher
    return {"active_devices": list(k for k, v in alert_watcher._active.items() if v)}


# ── OCR ──────────────────────────────────────────────────────────

@router.post("/ocr/recognize")
async def ocr_recognize(data: dict) -> dict[str, Any]:
    from app.services.ocr_service import ocr_service
    udid = data["udid"]
    wda_port = data.get("wda_port", 8100)
    texts = await ocr_service.recognize_from_page_source(udid, wda_port)
    return {"ok": True, "elements": texts}


@router.post("/ocr/find-text")
async def ocr_find_text(data: dict) -> dict[str, Any]:
    from app.services.ocr_service import ocr_service
    found = await ocr_service.find_text_on_screen(
        udid=data["udid"],
        target=data["target"],
        wda_port=data.get("wda_port", 8100),
    )
    return {"ok": found is not None, "element": found}


@router.get("/ocr/status")
async def ocr_status() -> dict[str, Any]:
    from app.services.ocr_service import ocr_service
    return {"ready": ocr_service.ready}


# ── Telegram Notifications ──────────────────────────────────────

@router.post("/telegram/send")
async def send_telegram(data: dict) -> dict[str, Any]:
    from app.services.action_logger import log_info
    msg_type = data.get("type", "info")
    device = data.get("device", "unknown")
    message = data.get("message", "")

    await log_info("telegram_send", type=msg_type, device=device)

    try:
        from app.database import SessionLocal
        from app.models.app_settings import AppSettings
        from sqlalchemy import select

        async with SessionLocal() as session:
            token_row = (await session.execute(
                select(AppSettings).where(AppSettings.key == "telegram_bot_token")
            )).scalar_one_or_none()
            chat_row = (await session.execute(
                select(AppSettings).where(AppSettings.key == "telegram_chat_ids")
            )).scalar_one_or_none()

            if token_row and chat_row:
                chat_ids = [c.strip() for c in (chat_row.value or "").split(",") if c.strip()]
                import httpx
                url = f"https://api.telegram.org/bot{token_row.value}/sendMessage"
                async with httpx.AsyncClient(timeout=15.0) as client:
                    for cid in chat_ids:
                        await client.post(url, json={
                            "chat_id": cid, "text": message or f"[{msg_type}] {device}",
                            "parse_mode": "Markdown",
                        })
                await log_info("telegram_sent", type=msg_type, device=device)
                return {"ok": True, "sent": len(chat_ids)}

        return {"ok": False, "error": "Telegram not configured"}

    except Exception as e:
        return {"ok": False, "error": str(e)}
