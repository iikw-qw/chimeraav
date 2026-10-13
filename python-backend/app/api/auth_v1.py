"""Auth v1 router — hardware-binding, code-based auth, register/login."""
from __future__ import annotations
import os

import hashlib
import platform
import random
import socket
import subprocess
import time
import uuid

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import select

from app.database import SessionLocal
from app.models.app_settings import AppSettings

router = APIRouter(prefix="/v1/auth", tags=["auth-v1"])

BOT_SECRET = os.environ["CHIMERA_BOT_SECRET"]

_codes_db: dict[str, dict] = {}
_devices_db: dict[str, dict] = {}


def _collect_hw() -> dict:
    m: dict = {}
    m["hostname"] = socket.gethostname()
    m["platform"] = platform.system()
    m["release"] = platform.release()
    m["machine"] = platform.machine()
    m["processor"] = platform.processor() or "unknown"
    m["mac"] = ":".join(f"{(uuid.getnode() >> i) & 0xff:02x}" for i in range(0, 48, 8))
    if platform.system() == "Windows":
        for label, cmd in (
            ("bios_serial", ["wmic", "bios", "get", "serialnumber"]),
            ("board_serial", ["wmic", "baseboard", "get", "serialnumber"]),
            ("disk_serial", ["wmic", "diskdrive", "get", "serialnumber"]),
        ):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                m[label] = r.stdout.strip().split("\n")[-1].strip()
            except Exception:
                m[label] = "n/a"
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            m["machine_guid"] = winreg.QueryValueEx(key, "MachineGuid")[0]
        except Exception:
            m["machine_guid"] = "n/a"
    try:
        import psutil
        m["ram_gb"] = round(psutil.virtual_memory().total / 1073741824, 1)
        m["cpu_count"] = psutil.cpu_count(logical=False) or psutil.cpu_count()
        m["cpu_pct"] = psutil.cpu_percent(0.3)
        m["ram_pct"] = psutil.virtual_memory().percent
        m["disk_pct"] = psutil.disk_usage("/").percent
        m["boot_time"] = int(psutil.boot_time())
        m["process_count"] = len(psutil.pids())
    except Exception:
        pass
    return m


def _hw_hash(metrics: dict | None = None) -> str:
    if not metrics:
        metrics = _collect_hw()
    stable_keys = [
        "hostname", "platform", "machine", "processor", "mac",
        "bios_serial", "board_serial", "disk_serial", "machine_guid",
        "ram_gb", "cpu_count",
    ]
    parts = sorted(f"{k}={metrics.get(k, 'n/a')}" for k in stable_keys if k in metrics)
    raw = "|".join(parts) + "|CHIMERA_SALT_2025"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _hardware_id() -> str:
    return _hw_hash()


def _host_info() -> dict:
    m = _collect_hw()
    m["hardware_id"] = _hw_hash(m)
    return m


async def _get_setting(session, key: str):
    row = (await session.execute(
        select(AppSettings).where(AppSettings.key == key)
    )).scalar_one_or_none()
    return row.value if row else None


async def _set_setting(session, key: str, value):
    row = (await session.execute(
        select(AppSettings).where(AppSettings.key == key)
    )).scalar_one_or_none()
    if row:
        row.value = value
    else:
        session.add(AppSettings(key=key, value=value))


@router.post("/register")
async def chimera_auth_register(data: dict):
    code = str(random.randint(100000, 999999))
    hw = _hardware_id()
    try:
        async with SessionLocal() as session:
            existing_email = await _get_setting(session, "user_email")
            if existing_email and existing_email == data.get("email", ""):
                stored_hw = await _get_setting(session, "user_hardware_id")
                if stored_hw and stored_hw != hw:
                    return {"detail": "This app is bound to a different computer"}
                await _set_setting(session, "auth_verification_code", code)
                await _set_setting(session, "user_hardware_id", hw)
                await session.commit()
                return {"token": "local_" + code, "verification_code": code, "hardware_id": hw}

            await _set_setting(session, "user_email", data.get("email", ""))
            await _set_setting(session, "user_telegram", data.get("telegram_username", ""))
            await _set_setting(session, "auth_verification_code", code)
            await _set_setting(session, "user_hardware_id", hw)
            await session.commit()
            return {"token": "local_" + code, "verification_code": code, "hardware_id": hw}
    except Exception as ex:
        return {"token": "err_" + code, "verification_code": code, "hardware_id": hw, "db_warn": str(ex)}


@router.post("/login")
async def chimera_auth_login(data: dict):
    hw = _hardware_id()
    try:
        async with SessionLocal() as session:
            row = (await session.execute(
                select(AppSettings).where(AppSettings.key == "user_email")
            )).scalar_one_or_none()
            stored_email = row.value if row else None
            if not stored_email or stored_email != data.get("email", ""):
                return {"detail": "User not found"}

            hw_row = (await session.execute(
                select(AppSettings).where(AppSettings.key == "user_hardware_id")
            )).scalar_one_or_none()
            stored_hw = hw_row.value if hw_row else None
            if stored_hw and stored_hw != hw:
                return {"detail": "App is bound to a different computer"}

            if hw_row:
                hw_row.value = hw
            else:
                session.add(AppSettings(key="user_hardware_id", value=hw))
            await session.commit()
            return {"token": stored_email}
    except Exception as ex:
        return {"detail": str(ex)}


@router.get("/test")
async def chimera_auth_test():
    return {"ok": True, "hw": _hardware_id()[:12], "port": "working"}


@router.post("/get-code")
async def chimera_get_code():
    metrics = _collect_hw()
    hw = _hw_hash(metrics)
    if hw in _devices_db and _devices_db[hw].get("verified"):
        return {
            "already_authorized": True,
            "hardware_id": hw[:12],
            "telegram_username": _devices_db[hw].get("telegram_username", ""),
            "trust_score": _devices_db[hw].get("trust_score", 70),
        }

    try:
        async with SessionLocal() as session:
            row = (await session.execute(
                select(AppSettings).where(AppSettings.key == "auth_telegram_id")
            )).scalar_one_or_none()
            hw_row = (await session.execute(
                select(AppSettings).where(AppSettings.key == "user_hardware_id")
            )).scalar_one_or_none()
            tg_user_row = (await session.execute(
                select(AppSettings).where(AppSettings.key == "auth_telegram_username")
            )).scalar_one_or_none()
            verified_row = (await session.execute(
                select(AppSettings).where(AppSettings.key == "auth_device_verified")
            )).scalar_one_or_none()
            if (verified_row and verified_row.value is True
                    and hw_row and hw_row.value == hw
                    and row and row.value):
                _devices_db[hw] = {
                    "verified": True,
                    "telegram_id": row.value,
                    "telegram_username": tg_user_row.value if tg_user_row else "",
                    "trust_score": 85,
                }
                return {
                    "already_authorized": True,
                    "hardware_id": hw[:12],
                    "telegram_username": tg_user_row.value if tg_user_row else "",
                }
    except Exception:
        pass

    active_codes = sum(
        1 for c in _codes_db.values()
        if c["hardware_id"] == hw and time.time() - c["created_at"] < 3600
    )
    if active_codes >= 3:
        return {"error": "Too many code requests. Wait an hour.", "rate_limited": True}

    code = str(random.randint(100000, 999999))
    _codes_db[code] = {
        "hardware_id": hw, "created_at": time.time(),
        "verified": False, "attempts": 3, "metrics": metrics,
    }
    _devices_db[hw] = {"code": code, "verified": False}

    try:
        async with SessionLocal() as session:
            await _set_setting(session, "auth_pending_code", code)
            await _set_setting(session, "user_hardware_id", hw)
            await session.commit()
    except Exception:
        pass

    return {
        "code": code,
        "hardware_id": hw[:12],
        "expires_in": 300,
        "instruction": "Send to bot in Telegram: /verify " + code,
        "metrics_collected": list(metrics.keys()),
    }


@router.post("/check")
async def chimera_check_auth():
    hw = _hardware_id()
    if hw in _devices_db and _devices_db[hw].get("verified"):
        return {
            "authorized": True,
            "telegram_username": _devices_db[hw].get("telegram_username", ""),
            "trust_score": _devices_db[hw].get("trust_score", 70),
        }

    try:
        async with SessionLocal() as session:
            verified_row = (await session.execute(
                select(AppSettings).where(AppSettings.key == "auth_device_verified")
            )).scalar_one_or_none()
            hw_row = (await session.execute(
                select(AppSettings).where(AppSettings.key == "user_hardware_id")
            )).scalar_one_or_none()
            tg_row = (await session.execute(
                select(AppSettings).where(AppSettings.key == "auth_telegram_username")
            )).scalar_one_or_none()
            if (verified_row and verified_row.value is True
                    and hw_row and hw_row.value == hw):
                _devices_db[hw] = {
                    "verified": True,
                    "telegram_username": tg_row.value if tg_row else "",
                    "trust_score": 85,
                }
                return {"authorized": True, "telegram_username": tg_row.value if tg_row else ""}
    except Exception:
        pass

    return {"authorized": False}


@router.post("/verify-from-bot")
async def chimera_verify_from_bot(
    data: dict,
    x_bot_secret: str | None = Header(None),
):
    if x_bot_secret != BOT_SECRET:
        raise HTTPException(status_code=403, detail="Invalid bot secret")

    code = str(data.get("code", ""))
    telegram_id = data.get("telegram_id")
    telegram_username = data.get("telegram_username", "")

    if code not in _codes_db:
        return {"ok": False, "error": "Code not found or expired"}

    entry = _codes_db[code]
    if time.time() - entry["created_at"] > 300:
        del _codes_db[code]
        return {"ok": False, "error": "Code expired (5 minutes)"}

    entry["attempts"] -= 1
    if entry["attempts"] <= 0:
        del _codes_db[code]
        return {"ok": False, "error": "Too many attempts"}

    for hw_id, dev in _devices_db.items():
        if dev.get("telegram_id") == telegram_id and dev.get("verified") and hw_id != entry["hardware_id"]:
            return {"ok": False, "error": "This Telegram account is already bound to another device"}

    hw = entry["hardware_id"]
    del _codes_db[code]
    _devices_db[hw] = {
        "verified": True, "telegram_id": telegram_id,
        "telegram_username": telegram_username, "code": code,
        "trust_score": 70, "verified_at": time.time(),
    }

    try:
        async with SessionLocal() as session:
            await _set_setting(session, "auth_telegram_id", str(telegram_id))
            await _set_setting(session, "auth_telegram_username", telegram_username)
            await _set_setting(session, "auth_device_verified", True)
            await _set_setting(session, "user_hardware_id", hw)
            await session.commit()
    except Exception:
        pass

    return {"ok": True, "hardware_id": hw[:12], "message": f"Device authorized for @{telegram_username}"}
