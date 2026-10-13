"""Common FastAPI dependencies and helpers."""

from __future__ import annotations

from typing import Annotated, TypeVar

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session as _get_session

get_session = _get_session

DbSession = Annotated[AsyncSession, Depends(_get_session)]

T = TypeVar("T")


async def get_or_404(session: AsyncSession, model: type[T], obj_id: str | int) -> T:
    obj = await session.get(model, obj_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj


def apply_update(instance: object, payload: BaseModel) -> None:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(instance, key, value)
