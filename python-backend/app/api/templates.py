from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message_template import MessageTemplate

from ._deps import apply_update, get_or_404, get_session

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplateBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    style: str
    template_text: str
    language: str = "en"
    is_active: bool = True


class TemplateCreate(TemplateBase):
    pass


class TemplateUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str | None = None
    style: str | None = None
    template_text: str | None = None
    language: str | None = None
    is_active: bool | None = None


class TemplateRead(TemplateBase):
    id: str
    created_at: datetime


@router.get("", response_model=list[TemplateRead])
async def list_templates(
    session: Annotated[AsyncSession, Depends(get_session)],
    style: str | None = None,
    language: str | None = None,
    active_only: bool = False,
) -> list[MessageTemplate]:
    stmt = select(MessageTemplate)
    if style:
        stmt = stmt.where(MessageTemplate.style == style)
    if language:
        stmt = stmt.where(MessageTemplate.language == language)
    if active_only:
        stmt = stmt.where(MessageTemplate.is_active.is_(True))
    stmt = stmt.order_by(MessageTemplate.created_at.desc())
    return list((await session.execute(stmt)).scalars().all())


@router.post("", response_model=TemplateRead, status_code=201)
async def create_template(
    payload: TemplateCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> MessageTemplate:
    tpl = MessageTemplate(**payload.model_dump())
    session.add(tpl)
    await session.commit()
    await session.refresh(tpl)
    return tpl


@router.get("/{template_id}", response_model=TemplateRead)
async def get_template(
    template_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> MessageTemplate:
    return await get_or_404(session, MessageTemplate, template_id)


@router.put("/{template_id}", response_model=TemplateRead)
async def update_template(
    template_id: str,
    payload: TemplateUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MessageTemplate:
    tpl = await get_or_404(session, MessageTemplate, template_id)
    apply_update(tpl, payload)
    await session.commit()
    await session.refresh(tpl)
    return tpl


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> Response:
    tpl = await get_or_404(session, MessageTemplate, template_id)
    await session.delete(tpl)
    await session.commit()
    return Response(status_code=204)
