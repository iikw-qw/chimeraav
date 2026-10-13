"""
API настроек (глобальные и пользовательские).
Зависит от: models/setting, schemas/common, deps, redis_client
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.setting import AppSetting
from app.models.user import User
from app.schemas.common import SettingUpdate, SettingResponse
from app.api.deps import get_current_user
from app.services.redis_client import redis_client

router = APIRouter()


@router.get("", response_model=list[SettingResponse])
async def get_settings(
    scope: Optional[str] = Query("all", description="all, global, user"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if scope == "global":
        query = select(AppSetting).where(AppSetting.user_id.is_(None))
    elif scope == "user":
        query = select(AppSetting).where(AppSetting.user_id == current_user.id)
    else:
        query = select(AppSetting).where(
            (AppSetting.user_id.is_(None)) | (AppSetting.user_id == current_user.id)
        )
    result = await db.execute(query)
    return [SettingResponse.model_validate(s) for s in result.scalars().all()]


@router.put("")
async def update_setting(
    data: SettingUpdate,
    is_global: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = None if is_global else current_user.id

    result = await db.execute(
        select(AppSetting).where(AppSetting.user_id == user_id, AppSetting.key == data.key)
    )
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = data.value
    else:
        setting = AppSetting(user_id=user_id, key=data.key, value=data.value)
        db.add(setting)

    await db.flush()

    if is_global:
        await redis_client.publish("chimera:settings_broadcast", {
            "key": data.key,
            "value": data.value,
        })

    return {"message": "Setting updated", "key": data.key}
