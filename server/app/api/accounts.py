"""
CRUD API для аккаунтов соцсетей.
Зависит от: models/account, schemas/account, deps
"""

from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.account import SocialAccount
from app.models.user import User
from app.schemas.account import AccountCreate, AccountUpdate, AccountResponse
from app.api.deps import get_current_user

router = APIRouter()


@router.get("", response_model=list[AccountResponse])
async def list_accounts(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    device_id: Optional[UUID] = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(SocialAccount).where(SocialAccount.user_id == current_user.id)
    if platform:
        query = query.where(SocialAccount.platform == platform)
    if status:
        query = query.where(SocialAccount.status == status)
    if device_id:
        query = query.where(SocialAccount.device_id == device_id)
    query = query.order_by(SocialAccount.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return [AccountResponse.model_validate(a) for a in result.scalars().all()]


@router.get("/count")
async def count_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.count(SocialAccount.id)).where(SocialAccount.user_id == current_user.id)
    )
    return {"total": result.scalar()}


@router.post("", response_model=AccountResponse, status_code=201)
async def create_account(
    data: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = SocialAccount(user_id=current_user.id, **data.model_dump())
    db.add(account)
    await db.flush()
    await db.refresh(account)
    return AccountResponse.model_validate(account)


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SocialAccount).where(SocialAccount.id == account_id, SocialAccount.user_id == current_user.id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return AccountResponse.model_validate(account)


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: UUID,
    data: AccountUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SocialAccount).where(SocialAccount.id == account_id, SocialAccount.user_id == current_user.id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(account, field, value)

    await db.flush()
    await db.refresh(account)
    return AccountResponse.model_validate(account)


@router.delete("/{account_id}")
async def delete_account(
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SocialAccount).where(SocialAccount.id == account_id, SocialAccount.user_id == current_user.id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    await db.delete(account)
    return {"message": "Account deleted"}
