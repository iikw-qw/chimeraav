from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.comment import Comment
from app.models.device import Device
from app.models.welcome_message import WelcomeMessage
from app.services.auto_login import perform_auto_login
from app.services.crypto import decrypt, encrypt
from app.services.email_sync import IMAP_SERVERS, EmailSync

from ._deps import apply_update, get_or_404, get_session

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    device_id: str
    platform: str
    username: str
    password_encrypted: str | None = None
    status: str = "active"
    posting_style: str = "friendly"
    auto_reply_enabled: bool = False
    welcome_message_enabled: bool = False
    auto_chatter_language: str = "en"
    notify_new_messages: bool = False
    activity_hours_min: int = 1
    activity_hours_max: int = 6
    warmup_stage: int = 0


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    platform: str | None = None
    username: str | None = None
    password_encrypted: str | None = None
    status: str | None = None
    posting_style: str | None = None
    auto_reply_enabled: bool | None = None
    welcome_message_enabled: bool | None = None
    auto_chatter_language: str | None = None
    notify_new_messages: bool | None = None
    activity_hours_min: int | None = None
    activity_hours_max: int | None = None
    warmup_stage: int | None = None


class AccountRead(AccountBase):
    id: str
    unique_code: str | None = None
    created_at: datetime


@router.get("", response_model=list[AccountRead])
async def list_accounts(
    session: Annotated[AsyncSession, Depends(get_session)],
    device_id: str | None = None,
    platform: str | None = None,
) -> list[Account]:
    stmt = select(Account)
    if device_id:
        stmt = stmt.where(Account.device_id == device_id)
    if platform:
        stmt = stmt.where(Account.platform == platform)
    stmt = stmt.order_by(Account.created_at.desc())
    return list((await session.execute(stmt)).scalars().all())


@router.post("", response_model=AccountRead, status_code=201)
async def create_account(
    payload: AccountCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> Account:
    account = Account(**payload.model_dump())
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


@router.get("/{account_id}", response_model=AccountRead)
async def get_account(
    account_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> Account:
    return await get_or_404(session, Account, account_id)


@router.put("/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: str,
    payload: AccountUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Account:
    account = await get_or_404(session, Account, account_id)
    apply_update(account, payload)
    await session.commit()
    await session.refresh(account)
    return account


@router.delete("/{account_id}", status_code=204)
async def delete_account(
    account_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> Response:
    account = await get_or_404(session, Account, account_id)
    await session.delete(account)
    await session.commit()
    return Response(status_code=204)


class WelcomeTogglePayload(BaseModel):
    enabled: bool = True


@router.post("/{account_id}/enable-welcome", response_model=AccountRead)
async def enable_welcome(
    account_id: str,
    payload: WelcomeTogglePayload,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Account:
    account = await get_or_404(session, Account, account_id)
    account.welcome_message_enabled = payload.enabled
    await session.commit()
    await session.refresh(account)
    return account


class NotificationsPayload(BaseModel):
    enabled: bool = True


@router.post("/{account_id}/enable-notifications", response_model=AccountRead)
async def enable_notifications(
    account_id: str,
    payload: NotificationsPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Account:
    account = await get_or_404(session, Account, account_id)
    account.notify_new_messages = payload.enabled
    await session.commit()
    await session.refresh(account)
    return account


async def _send_welcome_for_account(account_id: str, session: AsyncSession) -> int:
    stmt = select(Comment).where(
        Comment.account_id == account_id,
        Comment.welcome_sent.is_(False),
        Comment.commenter_gender == "male",
    )
    rows = list((await session.execute(stmt)).scalars().all())
    if not rows:
        return 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for c in rows:
        c.welcome_sent = True
        c.welcome_sent_at = now
        session.add(
            WelcomeMessage(
                account_id=c.account_id,
                comment_id=c.id,
                message_text="Hi! Nice to meet you!",
                language="en",
                status="sent",
            )
        )
    await session.commit()
    return len(rows)


@router.post("/{account_id}/send-welcome-bulk")
async def send_welcome_bulk(
    account_id: str,
    background: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    await get_or_404(session, Account, account_id)
    pending_stmt = (
        select(Comment)
        .where(
            Comment.account_id == account_id,
            Comment.welcome_sent.is_(False),
            Comment.commenter_gender == "male",
        )
    )
    pending = list((await session.execute(pending_stmt)).scalars().all())
    background.add_task(_run_welcome_job, account_id)
    return {
        "account_id": account_id,
        "queued": len(pending),
        "status": "scheduled",
    }


async def _run_welcome_job(account_id: str) -> None:
    from app.database import SessionLocal

    async with SessionLocal() as session:
        await _send_welcome_for_account(account_id, session)


class SetEmailIn(BaseModel):
    email: str
    email_password: str


@router.put("/{account_id}/email")
async def set_account_email(
    account_id: str,
    payload: SetEmailIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    account = await get_or_404(session, Account, account_id)
    account.email = payload.email
    account.email_password_encrypted = encrypt(payload.email_password)
    domain = payload.email.split("@")[1].lower()
    account.email_imap_server = IMAP_SERVERS.get(domain, f"imap.{domain}")
    await session.commit()
    return {"status": "ok"}


@router.get("/{account_id}/email")
async def get_account_email(
    account_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    account = await get_or_404(session, Account, account_id)
    return {
        "email": account.email,
        "has_password": bool(account.email_password_encrypted),
        "imap_server": account.email_imap_server,
    }


@router.post("/{account_id}/fetch-code")
async def fetch_auth_code(
    account_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    account = await get_or_404(session, Account, account_id)
    if not account.email:
        raise HTTPException(400, "Почта не привязана")
    if not account.email_password_encrypted:
        raise HTTPException(400, "Пароль от почты не задан")
    sync = EmailSync()
    code = await sync.fetch_auth_code(
        account.email, decrypt(account.email_password_encrypted), account.platform,
    )
    if code:
        return {"code": code}
    raise HTTPException(408, "Код не найден в почте за 2 минуты")


class AutoLoginIn(BaseModel):
    password: str | None = None


@router.post("/{account_id}/auto-login")
async def auto_login(
    account_id: str,
    payload: AutoLoginIn,
    background: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    account = await get_or_404(session, Account, account_id)
    device = await get_or_404(session, Device, account.device_id)
    if device.platform not in ("android", "ios"):
        return {
            "ok": False,
            "stage": "platform",
            "message": f"Авто-вход не поддерживается для платформы {device.platform}",
        }
    if not device.serial:
        return {
            "ok": False,
            "stage": "device",
            "message": "У устройства нет serial/UDID — переподключите телефон",
        }
    password = payload.password or account.password_encrypted or ""
    if not password:
        return {
            "ok": False,
            "stage": "credentials",
            "message": "Пароль не задан — добавьте его в карточке аккаунта",
        }
    email_pwd = None
    if account.email_password_encrypted:
        try:
            email_pwd = decrypt(account.email_password_encrypted)
        except Exception:
            pass
    background.add_task(
        perform_auto_login,
        account_id=account.id,
        device_id=device.id,
        serial=device.serial,
        platform=account.platform,
        username=account.username,
        password=password,
        device_platform=device.platform,
        account_email=account.email,
        account_email_password=email_pwd,
    )
    return {
        "ok": True,
        "stage": "scheduled",
        "message": f"Запускаю авто-вход для @{account.username}",
        "account_id": account.id,
        "device_id": device.id,
    }
