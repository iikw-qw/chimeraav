"""
API авторизации: регистрация, вход, верификация Telegram, профиль, привязка к железу.
Зависит от: auth_service, models/user, models/hardware, schemas/user
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.models.user import User
from app.models.hardware import HardwareLicense, HostMetric
from app.schemas.user import UserRegister, UserLogin, UserResponse, TokenResponse, VerifyTelegramRequest
from app.services.auth_service import (
    hash_password, verify_password, create_access_token,
    generate_verification_code, get_user_by_email,
)
from app.services.hardware_auth import get_hardware_id, get_host_info, get_host_metrics
from app.api.deps import get_current_user

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    existing = await get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    verification_code = generate_verification_code()
    hw = get_host_info()

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        telegram_username=data.telegram_username,
        verification_code=verification_code,
        app_version=settings.app_version,
        hardware_id=hw["hardware_id"],
        last_login_at=datetime.utcnow(),
        login_count=1,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    existing_license = await db.execute(
        select(HardwareLicense).where(HardwareLicense.hardware_id == hw["hardware_id"])
    )
    if not existing_license.scalar_one_or_none():
        license_entry = HardwareLicense(
            user_id=user.id,
            hardware_id=hw["hardware_id"],
            hostname=hw["hostname"],
            os_name=hw["os_name"],
            os_version=hw["os_version"],
            cpu_info=hw["cpu_info"],
            ram_gb=hw["ram_gb"],
            mac_address=hw["mac_address"],
        )
        db.add(license_entry)

    token = create_access_token({"sub": str(user.id)})
    user_data = UserResponse.model_validate(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_data.model_dump(mode="json"),
        "verification_code": verification_code,
        "hardware_id": hw["hardware_id"],
    }


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, data.email)
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    hw_id = get_hardware_id()
    result = await db.execute(
        select(HardwareLicense).where(
            HardwareLicense.user_id == user.id,
            HardwareLicense.hardware_id == hw_id,
            HardwareLicense.is_active.is_(True),
        )
    )
    hw_license = result.scalar_one_or_none()
    if not hw_license:
        existing_global = await db.execute(
            select(HardwareLicense).where(HardwareLicense.hardware_id == hw_id)
        )
        global_license = existing_global.scalar_one_or_none()
        if global_license:
            global_license.user_id = user.id
            global_license.last_seen_at = datetime.utcnow()
        else:
            hw = get_host_info()
            hw_license = HardwareLicense(
                user_id=user.id,
                hardware_id=hw_id,
                hostname=hw["hostname"],
                os_name=hw["os_name"],
                os_version=hw["os_version"],
                cpu_info=hw["cpu_info"],
                ram_gb=hw["ram_gb"],
                mac_address=hw["mac_address"],
            )
            db.add(hw_license)
    else:
        hw_license.last_seen_at = datetime.utcnow()

    if user.app_version != settings.app_version:
        user.app_version = settings.app_version
    user.last_login_at = datetime.utcnow()
    user.login_count = (user.login_count or 0) + 1

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.post("/verify-telegram")
async def verify_telegram(
    data: VerifyTelegramRequest,
    db: AsyncSession = Depends(get_db),
):
    """Верификация Telegram — может вызываться и из бота (без JWT), и из UI (с JWT)"""
    from app.services.auth_service import get_user_by_verification_code

    user = await get_user_by_verification_code(db, data.code)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    user.telegram_verified = True
    if data.telegram_id:
        user.telegram_id = data.telegram_id
    if data.telegram_username:
        user.telegram_username = data.telegram_username

    token = create_access_token({"sub": str(user.id)})
    return {"verified": True, "message": "Telegram verified successfully", "token": token}


@router.get("/metrics/host")
async def host_metrics():
    """Метрики хост-машины: CPU, RAM, диск, сеть."""
    metrics = get_host_metrics()
    metrics["hardware_id"] = get_hardware_id()
    return metrics


@router.get("/hardware-info")
async def hardware_info(current_user: User = Depends(get_current_user)):
    """Информация о текущем железе."""
    return get_host_info()
