"""Account registration API — auto-register accounts on social platforms."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, WebSocket
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account_registration import AccountRegistration
from app.models.device import Device
from app.services.account_registrator import account_registrator

from ._deps import get_or_404, get_session

router = APIRouter(prefix="/registration", tags=["registration"])


class RegisterNewRequest(BaseModel):
    email: str
    email_password: str
    platform: str
    device_id: str


class RegistrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    platform: str
    target_username: str | None = None
    status: str
    error_message: str | None = None
    device_id: str | None = None
    created_at: datetime


@router.get("", response_model=list[RegistrationRead])
async def list_registrations(
    session: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
) -> list[AccountRegistration]:
    stmt = select(AccountRegistration).order_by(AccountRegistration.created_at.desc())
    if status:
        stmt = stmt.where(AccountRegistration.status == status)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/register-new", response_model=dict, status_code=202)
async def register_new_account(
    payload: RegisterNewRequest,
    background: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    device = await get_or_404(session, Device, payload.device_id)

    background.add_task(
        account_registrator.register_account,
        device_id=payload.device_id,
        platform=payload.platform,
        email_addr=payload.email,
        email_password=payload.email_password,
        device_serial=device.serial,
    )

    return {
        "ok": True,
        "message": f"Регистрация {payload.platform} на {device.name} запущена",
        "device_id": payload.device_id,
        "platform": payload.platform,
    }


@router.get("/{registration_id}", response_model=RegistrationRead)
async def get_registration(
    registration_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AccountRegistration:
    return await get_or_404(session, AccountRegistration, registration_id)


@router.post("/devices/{device_id}/install-agent")
async def install_agent_on_device(
    device_id: str,
    background: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    device = await get_or_404(session, Device, device_id)
    if not device.serial:
        return {"ok": False, "error": "Устройство не имеет serial — подключите через USB"}

    from app.services.apk_deployer import apk_deployer

    background.add_task(apk_deployer.deploy_to_device, device.serial)
    return {
        "ok": True,
        "message": f"Установка агента на {device.name} запущена",
        "device_id": device_id,
    }
