from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_config
from app.database import DB_PATH
from app.models.app_settings import AppSettings
from app.services.antidetect import set_behavior_profile, set_captcha_key

from ._deps import get_session

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    value: Any
    updated_at: datetime


class SettingsPayload(BaseModel):
    items: dict[str, Any]


@router.get("", response_model=dict[str, Any])
async def get_settings(session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, Any]:
    rows = list((await session.execute(select(AppSettings))).scalars().all())
    return {row.key: row.value for row in rows}


@router.put("", response_model=dict[str, Any])
async def put_settings(
    payload: SettingsPayload, session: Annotated[AsyncSession, Depends(get_session)]
) -> dict[str, Any]:
    if not payload.items:
        return {}
    keys = list(payload.items.keys())
    existing = list(
        (
            await session.execute(select(AppSettings).where(AppSettings.key.in_(keys)))
        ).scalars().all()
    )
    by_key = {row.key: row for row in existing}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for key, value in payload.items.items():
        if key in by_key:
            by_key[key].value = value
            by_key[key].updated_at = now
        else:
            session.add(AppSettings(key=key, value=value, updated_at=now))
    await session.commit()

    # Runtime propagation for settings that back live singletons.
    if "human_behavior_profile" in payload.items:
        profile = str(payload.items["human_behavior_profile"] or "normal")
        if profile in ("calm", "normal", "fast"):
            set_behavior_profile(profile)  # type: ignore[arg-type]
    if "twocaptcha_api_key" in payload.items:
        set_captcha_key(str(payload.items["twocaptcha_api_key"] or ""))

    rows = list(
        (
            await session.execute(select(AppSettings).where(AppSettings.key.in_(keys)))
        ).scalars().all()
    )
    return {row.key: row.value for row in rows}


def _backup_dir() -> Path:
    return Path(app_config.data_dir) / "backups"


@router.post("/backup-now")
async def backup_now() -> dict[str, Any]:
    """Snapshot the SQLite DB into data_dir/backups, prune to keep_last."""
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="database file not yet initialised")
    backups = _backup_dir()
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = backups / f"chimera-{stamp}.db"
    shutil.copy2(DB_PATH, target)

    # Honour `backup_keep` if set.
    async with SessionLocal_proxy() as session:
        row = (
            await session.execute(
                select(AppSettings).where(AppSettings.key == "backup_keep")
            )
        ).scalar_one_or_none()
    keep = 14
    if row is not None:
        try:
            keep = max(1, int(row.value))
        except (TypeError, ValueError):
            keep = 14

    snaps = sorted(
        (p for p in backups.glob("chimera-*.db") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    pruned = 0
    for old in snaps[keep:]:
        try:
            old.unlink()
            pruned += 1
        except OSError:
            pass

    return {
        "ok": True,
        "path": target.as_posix(),
        "size_bytes": target.stat().st_size,
        "pruned": pruned,
        "kept": min(len(snaps), keep),
    }


def SessionLocal_proxy():  # late import shim to avoid circularity
    from app.database import SessionLocal
    return SessionLocal()
