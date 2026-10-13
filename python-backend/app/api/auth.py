"""Authorisation — one-time per app version, confirmed by the shared bot.

Flow:
  1. App boots → frontend calls GET /api/auth/status with current app version.
     If install is bound and saved version matches, returns {authorised: true}.
  2. Otherwise frontend calls POST /api/auth/code → server generates a 6-digit
     code, persists it tied to install_id, returns it for display.
  3. User opens chimera bot → /start <code> → bot confirms via
     POST /api/auth/bot-confirm. Server marks install_id authorised for the
     current version, stores telegram_id.
  4. Frontend polls /api/auth/status until authorised:true, then unlocks UI.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_settings import AppSettings

from ._deps import get_session

router = APIRouter(prefix="/auth", tags=["auth"])

_KEYS = {
    "install_id":   "auth_install_id",
    "auth_version": "auth_version",
    "auth_code":    "auth_pending_code",
    "auth_telegram":"auth_telegram_id",
}


async def _get(session: AsyncSession, key: str) -> str | None:
    row = (
        await session.execute(select(AppSettings).where(AppSettings.key == key))
    ).scalar_one_or_none()
    if row is None:
        return None
    return None if row.value is None else str(row.value)


async def _set(session: AsyncSession, key: str, value: str | None) -> None:
    row = (
        await session.execute(select(AppSettings).where(AppSettings.key == key))
    ).scalar_one_or_none()
    if row is None:
        session.add(AppSettings(key=key, value=value))
    else:
        row.value = value


class StatusOut(BaseModel):
    authorised: bool
    install_id: str
    version: str
    bound_telegram: str | None = None


@router.get("/status", response_model=StatusOut)
async def auth_status(
    version: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StatusOut:
    install_id = await _get(session, _KEYS["install_id"])
    if install_id is None:
        install_id = secrets.token_hex(8)
        await _set(session, _KEYS["install_id"], install_id)
        await session.commit()

    saved_version = await _get(session, _KEYS["auth_version"])
    bound_tg = await _get(session, _KEYS["auth_telegram"])
    authorised = saved_version == version and bound_tg is not None
    return StatusOut(
        authorised=authorised,
        install_id=install_id,
        version=version,
        bound_telegram=bound_tg,
    )


class CodeOut(BaseModel):
    code: str
    install_id: str


@router.post("/code", response_model=CodeOut)
async def issue_code(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CodeOut:
    install_id = await _get(session, _KEYS["install_id"])
    if install_id is None:
        install_id = secrets.token_hex(8)
        await _set(session, _KEYS["install_id"], install_id)

    code = f"{secrets.randbelow(1_000_000):06d}"
    await _set(session, _KEYS["auth_code"], code)
    await session.commit()
    return CodeOut(code=code, install_id=install_id)


class BotConfirmIn(BaseModel):
    telegram_id: str
    code: str


class BotConfirmOut(BaseModel):
    ok: bool
    install_id: str | None = None


@router.post("/bot-confirm", response_model=BotConfirmOut)
async def bot_confirm(
    payload: BotConfirmIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BotConfirmOut:
    saved_code = await _get(session, _KEYS["auth_code"])
    if saved_code is None or saved_code != payload.code:
        raise HTTPException(status_code=400, detail="invalid code")
    install_id = await _get(session, _KEYS["install_id"])
    if install_id is None:
        raise HTTPException(status_code=500, detail="install not initialised")

    # Bind: store telegram id and mark current app version authorised.
    await _set(session, _KEYS["auth_telegram"], payload.telegram_id)
    await _set(session, _KEYS["auth_version"], _CURRENT_VERSION)
    await _set(session, _KEYS["auth_code"], None)  # consume code
    await session.commit()
    return BotConfirmOut(ok=True, install_id=install_id)


@router.post("/sign-out")
async def sign_out(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    await _set(session, _KEYS["auth_version"], None)
    await _set(session, _KEYS["auth_telegram"], None)
    await session.commit()
    return {"ok": True}


# Bumped on every release — forces re-auth when version changes.
_CURRENT_VERSION = "9.0"


@router.get("/version")
async def current_version() -> dict:
    return {"version": _CURRENT_VERSION, "released": datetime.now(timezone.utc).isoformat()}
