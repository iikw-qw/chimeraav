"""Services v1 router — warmup, DM, poster, datasets, metrics, captions, agent, schedule."""
from __future__ import annotations

import asyncio
import glob as _glob
import json
import math
import os
import random
import re
from datetime import datetime, date, time as dt_time, timedelta, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from utils.ws_manager import ws_manager
from utils.validators import validate_device_platform

router = APIRouter(prefix="/v1", tags=["services-v1"])


# ── Warmup ──────────────────────────────────────────────────────────

_active_warmups: dict[str, dict] = {}


@router.post("/warmup/full")
async def v1_warmup_full(data: dict):
    from services.warmup_full import WarmupFull
    serial = data.get("serial")
    platform = data.get("platform", data.get("platforms", ["instagram"])[0] if data.get("platforms") else "instagram")
    platforms = data.get("platforms", [platform])
    validate_device_platform(serial, platform, platforms)
    w = WarmupFull(
        serial=serial,
        platform=platform,
        account_username=data.get("account"),
        account_user_id=data.get("account_user_id", 0),
    )
    _active_warmups[serial] = {"status": "running", "platform": platform}
    try:
        result = await w.run(
            data.get("duration"),
            data.get("intensity", 5),
            platforms=platforms,
            mode=data.get("mode", "single"),
            custom_weights=data.get("custom_weights"),
            custom_weights_per_platform=data.get("custom_weights_per_platform"),
            night_mode=data.get("night_mode", False),
            debug=data.get("debug", False),
        )
        _active_warmups[serial] = {"status": "finished", "stats": result}
        await ws_manager.broadcast(f"warmup_{serial}", {"event": "finished", "stats": result})
        return result
    except Exception:
        _active_warmups.pop(serial, None)
        raise


@router.get("/warmup/status/{serial}")
async def v1_warmup_status(serial: str):
    from services.warmup_full import is_warmup_active, is_warmup_paused
    info = _active_warmups.get(serial, {"status": "idle"})
    info["active"] = is_warmup_active(serial)
    info["paused"] = is_warmup_paused(serial)
    return info


@router.post("/warmup/stop/{serial}")
async def v1_warmup_stop(serial: str):
    from services.warmup_full import request_stop
    request_stop(serial)
    _active_warmups.pop(serial, None)
    return {"ok": True, "serial": serial}


@router.post("/warmup/pause/{serial}")
async def v1_warmup_pause(serial: str):
    from services.warmup_full import pause_warmup
    await pause_warmup(serial)
    return {"ok": True, "serial": serial, "paused": True}


@router.post("/warmup/unpause/{serial}")
async def v1_warmup_unpause(serial: str):
    from services.warmup_full import unpause_warmup
    await unpause_warmup(serial)
    return {"ok": True, "serial": serial, "paused": False}


@router.get("/warmup/report/{session_id}")
async def v1_warmup_report(session_id: str):
    from services.warmup_full import generate_warmup_report
    return await generate_warmup_report(session_id)


@router.get("/warmup/history/{serial}")
async def v1_warmup_history(serial: str):
    return {"sessions": []}


@router.post("/warmup/start-all")
async def v1_warmup_start_all(data: dict):
    from services.warmup_full import WarmupFull
    results = []
    try:
        from utils.adb_utils import adb_devices
        devs = adb_devices()
        serials = [d["serial"] for d in devs if d["state"] == "device"]
    except Exception:
        serials = []

    platforms = data.get("platforms", ["instagram"])
    intensity = data.get("intensity", 5)
    mode = data.get("mode", "single")

    for serial in serials:
        platform = platforms[0] if platforms else "instagram"
        w = WarmupFull(serial=serial, platform=platform)
        _active_warmups[serial] = {"status": "running", "platform": platform}
        asyncio.create_task(w.run(
            intensity=intensity,
            platforms=platforms,
            mode=mode,
        ))
        results.append({"serial": serial, "status": "started"})

    return {"started": len(results), "devices": results}


@router.post("/warmup/stop-all")
async def v1_warmup_stop_all():
    from services.warmup_full import request_stop
    stopped = []
    for serial in list(_active_warmups.keys()):
        request_stop(serial)
        stopped.append(serial)
    _active_warmups.clear()
    return {"stopped": len(stopped), "devices": stopped}


# ── Blacklist / Whitelist ──────────────────────────────────────────

@router.post("/warmup/blacklist")
async def v1_add_blacklist(data: dict):
    from services.warmup_full import add_to_blacklist
    return add_to_blacklist(data["username"], data["platform"], data.get("reason", ""))


@router.delete("/warmup/blacklist")
async def v1_remove_blacklist(data: dict):
    from services.warmup_full import remove_from_blacklist
    return remove_from_blacklist(data["username"], data["platform"])


@router.get("/warmup/blacklist")
async def v1_get_blacklist():
    from services.warmup_full import get_blacklist
    return get_blacklist()


@router.post("/warmup/whitelist")
async def v1_add_whitelist(data: dict):
    from services.warmup_full import add_to_whitelist
    return add_to_whitelist(data["username"], data["platform"], data.get("boost_factor", 2.0))


@router.delete("/warmup/whitelist")
async def v1_remove_whitelist(data: dict):
    from services.warmup_full import remove_from_whitelist
    return remove_from_whitelist(data["username"], data["platform"])


@router.get("/warmup/whitelist")
async def v1_get_whitelist():
    from services.warmup_full import get_whitelist
    return get_whitelist()


# ── Warmup Presets ─────────────────────────────────────────────────

@router.post("/warmup/presets")
async def v1_save_preset(data: dict):
    from services.warmup_full import save_preset
    return save_preset(
        data["name"], data.get("weights", {}), data.get("platforms", []),
        data.get("mode", "single"), data.get("intensity", 5), data.get("night_mode", False),
    )


@router.get("/warmup/presets")
async def v1_get_presets():
    from services.warmup_full import get_presets
    return get_presets()


@router.get("/warmup/presets/{preset_id}")
async def v1_get_preset(preset_id: int):
    from services.warmup_full import get_preset
    preset = get_preset(preset_id)
    if not preset:
        return {"error": "not found"}
    return preset


@router.delete("/warmup/presets/{preset_id}")
async def v1_delete_preset(preset_id: int):
    from services.warmup_full import delete_preset
    return delete_preset(preset_id)


# ── DM Scanner ──────────────────────────────────────────────────────

@router.post("/dm/scan")
async def v1_scan_dms(data: dict):
    from services.dm_scanner import DMScanner
    serial = data.get("serial", "")
    platform = data.get("platform", "instagram")
    validate_device_platform(serial, platform)
    s = DMScanner(serial, platform)
    return await s.process_dms()


@router.post("/dm/save")
async def v1_save_dm(data: dict):
    return {"ok": True, "saved": data.get("username", "")}


@router.get("/dm/list")
async def v1_dm_list(serial: str | None = None, platform: str | None = None, gender: str | None = None):
    from services.dm_scanner import get_contacts
    return get_contacts(serial, platform, gender)


@router.get("/dm/export")
async def v1_dm_export(format: str = "json"):
    from services.dm_scanner import export_contacts
    from fastapi.responses import PlainTextResponse
    result = export_contacts(format)
    if format == "csv":
        return PlainTextResponse(content=result, media_type="text/csv")
    return result


# ── Captions ───────────────────────────────────────────────────────

@router.post("/captions/generate")
async def v1_generate_caption(data: dict):
    from services.caption_generator import generate_caption
    return await generate_caption(
        tone=data.get("tone", "neutral"),
        include_hashtags=data.get("include_hashtags", True),
        hashtag_count=data.get("hashtag_count", 5),
    )


@router.get("/captions/random")
async def v1_random_captions(tone: str = "neutral", count: int = 5):
    from services.caption_generator import get_random_captions
    return await get_random_captions(tone, count)


# ── Poster ──────────────────────────────────────────────────────────

@router.get("/posts/prime-times")
async def v1_prime_times(region: str | None = None):
    from services.poster_v2 import PosterV2
    if region:
        return PosterV2.get_prime_times_for_region(region)
    return PosterV2.get_all_prime_times()


@router.post("/posts/import-photos")
async def v1_import_photos(data: dict):
    from services.poster_v2 import PosterV2
    p = PosterV2(data["serial"])
    p.import_photos(data["paths"])
    return {"ok": True, "count": len(data["paths"])}


@router.post("/posts/publish")
async def v1_publish_post(data: dict):
    from services.poster import Poster
    p = Poster(data["serial"])
    return await p.post(data["photos"], data.get("caption", ""), data.get("platform", "instagram"))


@router.post("/posts/publish-now")
async def v1_publish_now(data: dict):
    from services.poster_v2 import PosterV2
    from sqlalchemy import select as _sel
    from app.database import SessionLocal
    from app.models.app_settings import AppSettings

    serial = data.get("serial")
    platform_name = data.get("platform", "instagram")
    validate_device_platform(serial, platform_name)

    photos = data.get("photos", data.get("photo_paths", []))
    caption = data.get("caption", "")

    last_count = None
    try:
        async with SessionLocal() as session:
            row = (await session.execute(
                _sel(AppSettings).where(AppSettings.key == "last_photo_count")
            )).scalar_one_or_none()
            if row and row.value:
                last_count = int(row.value)
    except Exception:
        pass

    photo_count = PosterV2.resolve_photo_count(data.get("photo_count"), last_count)

    try:
        async with SessionLocal() as session:
            row = (await session.execute(
                _sel(AppSettings).where(AppSettings.key == "last_photo_count")
            )).scalar_one_or_none()
            if row:
                row.value = str(photo_count)
            else:
                session.add(AppSettings(key="last_photo_count", value=str(photo_count)))
            await session.commit()
    except Exception:
        pass

    if photos:
        p = PosterV2(serial)
        result = p.post_now(platform_name, photos[:photo_count], caption)
        return result

    return {"ok": True, "serial": serial, "photo_count": photo_count, "platform": platform_name}


@router.post("/posts/publish-prime")
async def v1_publish_prime(data: dict):
    from services.poster_v2 import PosterV2
    serial = data.get("serial")
    platform_name = data.get("platform", "instagram")
    validate_device_platform(serial, platform_name)
    region = data.get("region", "us")
    next_time = PosterV2.get_prime_time(region)
    return {
        "ok": True,
        "serial": serial,
        "platform": platform_name,
        "scheduled_at": next_time,
        "region": region,
    }


@router.post("/posts/draft")
async def v1_save_draft(data: dict):
    return {"ok": True, "draft_id": random.randint(1000, 9999), **data}


# ── Devices ─────────────────────────────────────────────────────────

from agent.stream_agent import stream_agent


@router.post("/devices/install-agent")
async def v1_install_agent_all():
    results = stream_agent.install_on_all()
    ok = sum(1 for r in results if r.get("ok"))
    fail = len(results) - ok
    return {"total": len(results), "installed": ok, "failed": fail, "details": results}


@router.post("/devices/{serial}/install-agent")
async def v1_install_agent_one(serial: str):
    return stream_agent.install_on_device(serial)


@router.post("/devices/sync")
async def v1_sync_devices():
    """Synchronize ADB devices with DB (v1 alias)."""
    from app.api.devices import perform_scan
    from app.database import SessionLocal
    async with SessionLocal() as session:
        devices, android_ok, ios_ok = await perform_scan(session)
        online = sum(1 for d in devices if d.status == "online")
    return {
        "ok": True,
        "adb_devices": len(devices),
        "online": online,
        "synced": True,
        "android_available": android_ok,
        "ios_available": ios_ok,
    }


@router.get("/devices/{serial}/platforms")
async def v1_device_platforms(serial: str, force: bool = False):
    from services.platform_detector import (
        get_cached_platforms,
        detect_and_save_platforms,
        detect_platforms,
    )
    if not force:
        cached = get_cached_platforms(serial)
        if cached is not None:
            return cached
    try:
        return await detect_and_save_platforms(serial)
    except Exception:
        return detect_platforms(serial)


@router.post("/devices/{serial}/launch")
async def v1_launch_platform(serial: str, data: dict):
    from services.platform_detector import launch_platform
    ok = await launch_platform(serial, data["package"])
    return {"ok": ok, "serial": serial, "package": data["package"]}


@router.get("/devices/{serial}/antidetect")
async def v1_antidetect_test(serial: str):
    from services.antidetect import AntiDetect
    return AntiDetect(serial).test()


@router.post("/devices/{serial}/proxy")
async def v1_set_proxy(serial: str, data: dict):
    from services.proxy_setup import ProxySetup
    p = ProxySetup(serial)
    if data.get("clear"):
        p.clear()
        return {"ok": True, "action": "cleared"}
    p.set_wifi(data["host"], data["port"])
    return {"ok": True, "ip": p.check_ip(), "vpn_apps": p.find_vpn_apps()}


@router.get("/devices/{serial}/health")
async def v1_device_health(serial: str):
    from utils.adb_utils import adb_cmd
    bat = adb_cmd(serial, ["shell", "dumpsys", "battery"], timeout=5).stdout
    level = 0
    temp = 0.0
    for line in bat.split("\n"):
        if "level:" in line:
            m = re.search(r"(\d+)", line)
            if m:
                level = int(m.group(1))
        if "temperature:" in line:
            m = re.search(r"(\d+)", line)
            if m:
                temp = int(m.group(1)) / 10

    storage = adb_cmd(serial, ["shell", "df", "/sdcard"], timeout=5).stdout
    free_mb = 0
    total_mb = 0
    lines = storage.strip().split("\n")
    if len(lines) > 1:
        parts = lines[1].split()
        if len(parts) >= 4:
            try:
                total_mb = int(parts[1]) // 1024
                free_mb = int(parts[3]) // 1024
            except (ValueError, IndexError):
                pass

    uptime_out = adb_cmd(serial, ["shell", "cat", "/proc/uptime"], timeout=5).stdout
    uptime_hours = 0.0
    m = re.search(r"([\d.]+)", uptime_out)
    if m:
        uptime_hours = round(float(m.group(1)) / 3600, 1)

    return {
        "serial": serial,
        "battery_percent": level,
        "temperature_c": temp,
        "storage_free_mb": free_mb,
        "storage_total_mb": total_mb,
        "uptime_hours": uptime_hours,
    }


# ── Agent install (scrcpy-based) ───────────────────────────────────

@router.post("/agent/install/{serial}")
async def v1_agent_install(serial: str):
    from agent.chimera_agent import install_agent
    return await install_agent(serial)


@router.get("/agent/status/{serial}")
async def v1_agent_status(serial: str):
    from agent.chimera_agent import get_agent_status
    return await get_agent_status(serial)


# ── Fix Everything (one-click device setup) ────────────────────────

@router.post("/devices/{serial}/fix-everything")
async def v1_fix_everything(serial: str):
    from services.device_setup import fix_everything
    return await fix_everything(serial)


@router.post("/devices/{serial}/cancel-setup")
async def v1_cancel_setup(serial: str):
    from services.device_setup import cancel_setup
    await cancel_setup(serial)
    return {"ok": True, "serial": serial}


@router.post("/devices/fix-all")
async def v1_fix_all_devices():
    from services.device_setup import fix_all_devices
    return await fix_all_devices()


@router.post("/devices/{serial}/self-test")
async def v1_self_test(serial: str):
    from services.device_setup import run_agent_self_test
    return await run_agent_self_test(serial)


@router.get("/devices/heartbeat")
async def v1_device_heartbeat():
    from services.device_heartbeat import get_all_device_status
    return get_all_device_status()


@router.post("/devices/troubleshoot")
async def v1_troubleshoot():
    from services.device_setup import troubleshoot
    return await troubleshoot()


# ── App Cloning / Multi-Account ────────────────────────────────────

@router.get("/devices/{serial}/clone-support")
async def v1_clone_support(serial: str):
    from services.app_cloner import check_clone_support
    return await check_clone_support(serial)


@router.get("/devices/{serial}/cloned-apps")
async def v1_cloned_apps(serial: str):
    from services.app_cloner import detect_cloned_apps
    return await detect_cloned_apps(serial)


@router.post("/devices/{serial}/enable-clone")
async def v1_enable_clone(serial: str, data: dict):
    from services.app_cloner import enable_dual_messenger
    return await enable_dual_messenger(serial, data["package"])


@router.post("/devices/{serial}/launch-clone")
async def v1_launch_clone(serial: str, data: dict):
    from services.app_cloner import launch_cloned_app
    ok = await launch_cloned_app(serial, data["package"], data.get("user_id", 0))
    return {"ok": ok, "serial": serial}


@router.get("/devices/{serial}/accounts")
async def v1_list_accounts(serial: str):
    from app.database import SessionLocal
    from app.models.account_mapping import AccountMapping
    from sqlalchemy import select

    try:
        async with SessionLocal() as session:
            rows = (await session.execute(
                select(AccountMapping).where(AccountMapping.serial == serial)
            )).scalars().all()
            return [
                {
                    "id": r.id,
                    "serial": r.serial,
                    "platform": r.platform,
                    "username": r.username,
                    "package_name": r.package_name,
                    "user_id": r.user_id,
                    "clone_method": r.clone_method,
                    "is_primary": r.is_primary,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
    except Exception:
        return []


@router.post("/devices/{serial}/accounts")
async def v1_create_account(serial: str, data: dict):
    from app.database import SessionLocal
    from app.models.account_mapping import AccountMapping

    try:
        async with SessionLocal() as session:
            mapping = AccountMapping(
                serial=serial,
                platform=data["platform"],
                username=data["username"],
                package_name=data["package_name"],
                user_id=data.get("user_id", 0),
                clone_method=data.get("clone_method", "main"),
                is_primary=data.get("is_primary", False),
            )
            session.add(mapping)
            await session.commit()
            await session.refresh(mapping)
            return {"ok": True, "id": mapping.id}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/devices/{serial}/accounts/{account_id}")
async def v1_delete_account(serial: str, account_id: int):
    from app.database import SessionLocal
    from app.models.account_mapping import AccountMapping
    from sqlalchemy import select

    try:
        async with SessionLocal() as session:
            row = (await session.execute(
                select(AccountMapping).where(
                    AccountMapping.id == account_id,
                    AccountMapping.serial == serial,
                )
            )).scalar_one_or_none()
            if not row:
                return {"ok": False, "error": "not found"}
            await session.delete(row)
            await session.commit()
            return {"ok": True, "id": account_id}
    except Exception:
        return {"ok": False, "error": "delete failed"}


# ── Device full status ──────────────────────────────────────────────

def _adb_getprop(serial: str, prop: str) -> str:
    from utils.adb_utils import adb_cmd
    try:
        return adb_cmd(serial, ["shell", "getprop", prop], timeout=5).stdout.strip()
    except Exception:
        return ""


def _get_package_version(serial: str, package: str) -> str:
    from utils.adb_utils import adb_cmd
    try:
        out = adb_cmd(serial, ["shell", "dumpsys", "package", package], timeout=10).stdout
        m = re.search(r"versionName=(\S+)", out)
        return m.group(1) if m else ""
    except Exception:
        return ""


@router.get("/devices/{serial}/full-status")
async def v1_device_full_status(serial: str):
    from services.platform_detector import detect_and_save_platforms, detect_platforms
    from services.device_setup import _check_package_installed, AGENT_PACKAGE

    model = _adb_getprop(serial, "ro.product.model")
    android = _adb_getprop(serial, "ro.build.version.release")

    agent_installed = await _check_package_installed(serial, AGENT_PACKAGE)
    agent_version = ""
    if agent_installed:
        agent_version = _get_package_version(serial, AGENT_PACKAGE)

    agent_running = False
    if agent_installed:
        try:
            from utils.adb_utils import adb_cmd as _adb_cmd
            ps = _adb_cmd(serial, ["shell", "pidof", AGENT_PACKAGE], timeout=5)
            agent_running = ps.stdout.strip() != ""
        except Exception:
            pass

    acc_enabled = False
    try:
        from utils.adb_utils import adb_cmd as _adb_cmd
        acc = _adb_cmd(serial, ["shell", "settings", "get", "secure",
             "enabled_accessibility_services"], timeout=5)
        acc_enabled = AGENT_PACKAGE in acc.stdout
    except Exception:
        pass

    try:
        platforms_data = await detect_and_save_platforms(serial)
    except Exception:
        platforms_data = detect_platforms(serial)

    battery = 0
    try:
        from utils.adb_utils import adb_cmd as _adb_cmd
        bat = _adb_cmd(serial, ["shell", "dumpsys", "battery"], timeout=5).stdout
        m = re.search(r"level:\s*(\d+)", bat)
        if m:
            battery = int(m.group(1))
    except Exception:
        pass

    return {
        "serial": serial,
        "model": model,
        "android_version": android,
        "online": True,
        "agent": {
            "installed": agent_installed,
            "version": agent_version,
            "running": agent_running,
        },
        "accessibility": {"enabled": acc_enabled},
        "platforms": platforms_data,
        "last_activity": None,
        "warmup_count": 0,
        "battery_percent": battery,
    }


# ── Datasets ────────────────────────────────────────────────────────

@router.post("/datasets/sync-to-device")
async def v1_sync_dataset(data: dict):
    serial = data["serial"]
    dataset_path = data["path"]
    from utils.adb_utils import adb_cmd as _adb_cmd
    files = _glob.glob(os.path.join(dataset_path, "*"))
    synced = 0
    for i, f in enumerate(files):
        name = os.path.basename(f)
        _adb_cmd(serial, ["push", f, f"/sdcard/DCIM/Camera/{name}"], timeout=30)
        synced += 1
        progress = int((i + 1) / len(files) * 100) if files else 100
        await ws_manager.broadcast("sync", {"device": serial, "file": name, "progress": progress})
    _adb_cmd(serial, ["shell",
         "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
         "-d", "file:///sdcard/DCIM/Camera/"], timeout=10)
    return {"ok": True, "synced": synced}


# ── Metrics ─────────────────────────────────────────────────────────

@router.get("/metrics/hardware")
async def chimera_hw_metrics():
    from app.api.auth_v1 import _host_info
    return _host_info()


# ── Schedule ────────────────────────────────────────────────────────

@router.post("/schedule/save")
async def v1_save_schedule(data: dict):
    return {"ok": True, "slots": len(data.get("slots", []))}


@router.post("/schedule/assign")
async def v1_assign_schedule(data: dict):
    serial = data.get("device_serial", data.get("serial"))
    platform = data.get("platform")
    validate_device_platform(serial, platform)
    return {
        "ok": True,
        "post_id": data.get("post_id"),
        "device_serial": serial,
        "platform": platform,
        "scheduled_at": data.get("scheduled_at"),
    }


@router.post("/schedule/batch-distribute")
async def v1_batch_distribute(data: dict):
    from services.caption_generator import generate_caption
    from services.poster_v2 import PosterV2

    serial = data.get("serial")
    platform = data.get("platform")
    validate_device_platform(serial, platform)

    dataset_id = data.get("dataset_id")
    photo_count_mode = data.get("photo_count_mode", "random")
    photo_count_fixed = data.get("photo_count_fixed", 5)
    caption_tone = data.get("caption_tone", "random")
    include_hashtags = data.get("include_hashtags", True)
    hashtag_count = data.get("hashtag_count", 5)
    distribution_mode = data.get("distribution_mode", "even")
    posts_per_day = data.get("posts_per_day", 3)
    start_date_str = data.get("start_date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    end_date_str = data.get("end_date", (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d"))
    region = data.get("region", "us")

    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    total_days = (end_dt - start_dt).days + 1
    total_posts = total_days * posts_per_day

    tones = ["playful", "flirty", "neutral", "professional", "motivational", "funny", "aesthetic"]
    prime_hours = {"us": (19, 21), "europe": (18, 20), "india": (19, 21), "uk": (18, 20)}
    region_hours = prime_hours.get(region, (19, 21))

    schedule = []
    for i in range(total_posts):
        day_offset = i // posts_per_day
        current_date = start_dt + timedelta(days=day_offset)
        if current_date > end_dt:
            break

        if distribution_mode == "even":
            slot_idx = i % posts_per_day
            hour = 8 + int((14 * slot_idx) / max(posts_per_day - 1, 1))
            minute = random.randint(0, 59)
        elif distribution_mode == "prime_only":
            hour = random.randint(region_hours[0], region_hours[1])
            minute = random.randint(0, 59)
        else:
            hour = random.randint(8, 22)
            minute = random.randint(0, 59)

        tone = random.choice(tones) if caption_tone == "random" else caption_tone
        photo_count = random.randint(1, 9) if photo_count_mode == "random" else photo_count_fixed

        scheduled_at = datetime.combine(current_date, dt_time(hour, minute))

        schedule.append({
            "post_index": i,
            "scheduled_at": scheduled_at.isoformat(),
            "photo_count": photo_count,
            "caption_tone": tone,
            "date": current_date.isoformat(),
        })

    return {
        "ok": True,
        "total_posts": len(schedule),
        "start": start_date_str,
        "end": end_date_str,
        "posts_per_day": posts_per_day,
        "schedule": schedule,
    }


@router.get("/schedule/upcoming")
async def v1_upcoming_posts(limit: int = 5):
    return []


@router.get("/schedule/posts")
async def v1_schedule_posts(
    serial: str | None = None,
    platform: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    from app.database import SessionLocal
    from app.models.scheduled_post import ScheduledPost
    from sqlalchemy import select, func

    try:
        async with SessionLocal() as session:
            q = select(ScheduledPost)
            count_q = select(func.count()).select_from(ScheduledPost)

            if serial:
                q = q.where(ScheduledPost.device_serial == serial)
                count_q = count_q.where(ScheduledPost.device_serial == serial)
            if platform:
                q = q.where(ScheduledPost.platform == platform)
                count_q = count_q.where(ScheduledPost.platform == platform)
            if status:
                q = q.where(ScheduledPost.status == status)
                count_q = count_q.where(ScheduledPost.status == status)

            total = await session.scalar(count_q) or 0
            rows = (await session.execute(
                q.order_by(ScheduledPost.scheduled_at.desc()).offset(offset).limit(limit)
            )).scalars().all()

            return {
                "total": total,
                "posts": [
                    {
                        "id": r.id,
                        "device_serial": r.device_serial,
                        "platform": r.platform,
                        "caption": r.caption,
                        "caption_style": r.caption_style,
                        "media_count": r.media_count,
                        "scheduled_at": r.scheduled_at.isoformat() if r.scheduled_at else None,
                        "status": r.status,
                        "retry_count": r.retry_count,
                        "last_error": r.last_error,
                        "hashtags": r.hashtags,
                        "location": r.location,
                        "is_prime_time": r.is_prime_time,
                        "posted_at": r.posted_at.isoformat() if r.posted_at else None,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ],
            }
    except Exception:
        return {"total": 0, "posts": []}


@router.get("/schedule/posts/{post_id}")
async def v1_schedule_post_detail(post_id: int):
    from app.database import SessionLocal
    from app.models.scheduled_post import ScheduledPost
    from sqlalchemy import select

    try:
        async with SessionLocal() as session:
            row = (await session.execute(
                select(ScheduledPost).where(ScheduledPost.id == post_id)
            )).scalar_one_or_none()
            if not row:
                return {"error": "not found"}
            return {
                "id": row.id,
                "device_serial": row.device_serial,
                "platform": row.platform,
                "caption": row.caption,
                "media_files": row.media_files,
                "media_count": row.media_count,
                "hashtags": row.hashtags,
                "location": row.location,
                "mentions": row.mentions,
                "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None,
                "status": row.status,
                "retry_count": row.retry_count,
                "last_error": row.last_error,
                "posted_at": row.posted_at.isoformat() if row.posted_at else None,
            }
    except Exception:
        return {"error": "not found"}


@router.put("/schedule/posts/{post_id}")
async def v1_update_scheduled_post(post_id: int, data: dict):
    from app.database import SessionLocal
    from app.models.scheduled_post import ScheduledPost
    from app.models._common import utc_now
    from sqlalchemy import select

    try:
        async with SessionLocal() as session:
            row = (await session.execute(
                select(ScheduledPost).where(ScheduledPost.id == post_id)
            )).scalar_one_or_none()
            if not row:
                return {"error": "not found"}
            for field in ("caption", "hashtags", "location", "mentions", "caption_style"):
                if field in data:
                    setattr(row, field, data[field])
            if "scheduled_at" in data:
                sa = datetime.fromisoformat(data["scheduled_at"])
                row.scheduled_at = sa
                row.scheduled_date = sa.date()
                row.scheduled_time = sa.time()
            row.updated_at = utc_now()
            await session.commit()
            return {"ok": True, "id": post_id}
    except Exception:
        return {"error": "update failed"}


@router.delete("/schedule/posts/{post_id}")
async def v1_delete_scheduled_post(post_id: int):
    from app.database import SessionLocal
    from app.models.scheduled_post import ScheduledPost
    from sqlalchemy import select

    try:
        async with SessionLocal() as session:
            row = (await session.execute(
                select(ScheduledPost).where(ScheduledPost.id == post_id)
            )).scalar_one_or_none()
            if not row:
                return {"error": "not found"}
            row.status = "cancelled"
            await session.commit()
            return {"ok": True, "id": post_id, "status": "cancelled"}
    except Exception:
        return {"error": "delete failed"}


@router.post("/schedule/posts/{post_id}/retry")
async def v1_retry_scheduled_post(post_id: int):
    from app.database import SessionLocal
    from app.models.scheduled_post import ScheduledPost
    from sqlalchemy import select

    try:
        async with SessionLocal() as session:
            row = (await session.execute(
                select(ScheduledPost).where(ScheduledPost.id == post_id)
            )).scalar_one_or_none()
            if not row:
                return {"error": "not found"}
            row.status = "pending"
            row.retry_count = 0
            row.last_error = None
            await session.commit()
            return {"ok": True, "id": post_id, "status": "pending"}
    except Exception:
        return {"error": "retry failed"}


@router.get("/posts/{post_id}/thumbnail")
async def v1_post_thumbnail(post_id: str):
    from fastapi.responses import Response
    return Response(content=b"", media_type="image/png")


# ── Telegram notifications ──────────────────────────────────────────

@router.post("/telegram/notify")
async def v1_telegram_notify(data: dict):
    chat_id = data.get("chat_id")
    message = data.get("message", "")
    if not chat_id or not message:
        return {"ok": False, "error": "chat_id and message required"}
    return {"ok": True, "sent": True}


# ── Stats ───────────────────────────────────────────────────────────

@router.get("/stats/daily")
async def v1_daily_stats():
    from services.warmup_full import _active_warmups as active
    return {
        "posts": 0,
        "likes": 0,
        "warmup_sessions": len(active),
        "active_warmups": len(active),
    }


@router.get("/stats/warmup-history")
async def v1_warmup_history_stats(days: int = 7):
    return {"days": days, "data": {}}


# ── Logs ────────────────────────────────────────────────────────────

@router.get("/logs")
async def v1_logs(limit: int = 20):
    log_file = os.path.join(os.environ.get("CHIMERA_LOG_DIR", "logs"), "chimera.log")
    if not os.path.exists(log_file):
        return []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
        entries = []
        for line in raw_lines[-limit:]:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
        return entries
    except Exception:
        return []


# ── Stream ──────────────────────────────────────────────────────────

@router.post("/stream/start/{serial}")
async def v1_stream_start(serial: str):
    validate_device_platform(serial, "any", ["any"])
    return stream_agent.start(serial)


@router.post("/stream/stop/{serial}")
async def v1_stream_stop(serial: str):
    return stream_agent.stop(serial)


@router.get("/stream/screenshot/{serial}")
async def v1_stream_screenshot(serial: str):
    return stream_agent.screenshot(serial)


# ── WebSocket routes ────────────────────────────────────────────────

ws_router = APIRouter()


@ws_router.websocket("/api/ws/warmup/{serial}")
async def ws_warmup(websocket: WebSocket, serial: str):
    room = f"warmup_{serial}"
    await ws_manager.connect(websocket, room)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, room)


@ws_router.websocket("/api/ws/warmup/{serial}/config")
async def ws_warmup_config(websocket: WebSocket, serial: str):
    room = f"warmup_config_{serial}"
    await ws_manager.connect(websocket, room)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "update_weights":
                    await ws_manager.broadcast(room, {"weights_updated": True, "weights": msg.get("weights", {})})
            except Exception:
                pass
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, room)


@ws_router.websocket("/api/ws/agent/{serial}")
async def ws_agent(websocket: WebSocket, serial: str):
    room = f"agent_install_{serial}"
    await ws_manager.connect(websocket, room)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, room)


@ws_router.websocket("/api/ws/stream/{serial}")
async def ws_stream(websocket: WebSocket, serial: str):
    room = f"stream_{serial}"
    await ws_manager.connect(websocket, room)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, room)


@ws_router.websocket("/api/ws/sync")
async def ws_sync(websocket: WebSocket):
    await ws_manager.connect(websocket, "sync")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, "sync")


@ws_router.websocket("/api/ws/setup/{serial}")
async def ws_setup(websocket: WebSocket, serial: str):
    room = f"setup_{serial}"
    await ws_manager.connect(websocket, room)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, room)


@ws_router.websocket("/api/ws/devices")
async def ws_devices(websocket: WebSocket):
    await ws_manager.connect(websocket, "devices")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, "devices")


@ws_router.websocket("/api/ws/logs")
async def ws_logs(websocket: WebSocket):
    await ws_manager.connect(websocket, "logs")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, "logs")
