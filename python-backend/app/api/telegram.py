from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_settings import AppSettings

from ._deps import get_session

router = APIRouter(prefix="/telegram", tags=["telegram"])

_SETTINGS_KEY = "telegram"


class TelegramSettings(BaseModel):
    bot_token: str | None = None
    chat_id: str | None = None
    enabled: bool = False
    notify_new_messages: bool = True
    notify_errors: bool = True


async def _load(session: AsyncSession) -> TelegramSettings:
    row = (
        await session.execute(select(AppSettings).where(AppSettings.key == _SETTINGS_KEY))
    ).scalar_one_or_none()
    if row is None or not isinstance(row.value, dict):
        return TelegramSettings()
    return TelegramSettings(**row.value)


async def _save(session: AsyncSession, settings: TelegramSettings) -> None:
    row = (
        await session.execute(select(AppSettings).where(AppSettings.key == _SETTINGS_KEY))
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if row is None:
        session.add(AppSettings(key=_SETTINGS_KEY, value=settings.model_dump(), updated_at=now))
    else:
        row.value = settings.model_dump()
        row.updated_at = now
    await session.commit()


@router.get("/settings", response_model=TelegramSettings)
async def get_telegram_settings(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TelegramSettings:
    return await _load(session)


@router.put("/settings", response_model=TelegramSettings)
async def put_telegram_settings(
    payload: TelegramSettings, session: Annotated[AsyncSession, Depends(get_session)]
) -> TelegramSettings:
    await _save(session, payload)
    return payload


class TelegramTestPayload(BaseModel):
    bot_token: str | None = None
    chat_id: str | None = None
    chat_ids: str | None = None  # comma-separated alternative


@router.post("/test")
async def test_telegram(
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: TelegramTestPayload | None = None,
) -> dict:
    cfg = await _load(session)
    bot_token = (payload.bot_token if payload else None) or cfg.bot_token
    chat_id = (payload.chat_id if payload else None) or cfg.chat_id
    if not chat_id and payload and payload.chat_ids:
        first = next(
            (s.strip() for s in payload.chat_ids.split(",") if s.strip()),
            None,
        )
        chat_id = first
    if not bot_token or not chat_id:
        raise HTTPException(400, "bot_token and chat_id are required")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": "Chimera test ping ✅",
                },
            )
        ok = r.status_code == 200 and r.json().get("ok") is True
        return {"ok": ok, "status_code": r.status_code, "response": r.json()}
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Telegram unreachable: {exc}") from exc


@router.get("/status")
async def telegram_status(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    cfg = await _load(session)
    return {
        "configured": bool(cfg.bot_token and cfg.chat_id),
        "enabled": cfg.enabled,
        "notify_new_messages": cfg.notify_new_messages,
        "notify_errors": cfg.notify_errors,
    }
