"""CRUD for caption templates + CSV import/export."""

from __future__ import annotations

import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.caption_template import CaptionTemplate

from ._deps import get_or_404, get_session

router = APIRouter(prefix="/captions", tags=["captions"])


class CaptionCreate(BaseModel):
    text: str
    category: str = "general"
    platform: str = "instagram"
    language: str = "en"


class CaptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    text: str
    category: str
    platform: str
    language: str


@router.get("", response_model=list[CaptionRead])
async def list_captions(
    session: Annotated[AsyncSession, Depends(get_session)],
    platform: str | None = None,
    category: str | None = None,
    language: str | None = None,
) -> list[CaptionTemplate]:
    stmt = select(CaptionTemplate)
    if platform:
        stmt = stmt.where(CaptionTemplate.platform == platform)
    if category:
        stmt = stmt.where(CaptionTemplate.category == category)
    if language:
        stmt = stmt.where(CaptionTemplate.language == language)
    stmt = stmt.order_by(CaptionTemplate.created_at.desc())
    return list((await session.execute(stmt)).scalars().all())


@router.post("", response_model=CaptionRead, status_code=201)
async def create_caption(
    payload: CaptionCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CaptionTemplate:
    row = CaptionTemplate(**payload.model_dump())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@router.delete("/{caption_id}", status_code=204)
async def delete_caption(
    caption_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    row = await get_or_404(session, CaptionTemplate, caption_id)
    await session.delete(row)
    await session.commit()


@router.post("/import")
async def import_captions(
    file: UploadFile,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    raw = (await file.read()).decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(io.StringIO(raw))
    count = 0
    for row in reader:
        text = row.get("text", "").strip()
        if not text:
            continue
        session.add(CaptionTemplate(
            text=text,
            category=row.get("category", "general").strip() or "general",
            platform=row.get("platform", "instagram").strip() or "instagram",
            language=row.get("language", "en").strip() or "en",
        ))
        count += 1
    await session.commit()
    return {"imported": count}


@router.get("/export")
async def export_captions(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    rows = list(
        (await session.execute(
            select(CaptionTemplate).order_by(CaptionTemplate.created_at.desc())
        )).scalars().all()
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["text", "category", "platform", "language"])
    writer.writeheader()
    for r in rows:
        writer.writerow({
            "text": r.text,
            "category": r.category,
            "platform": r.platform,
            "language": r.language,
        })
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=captions.csv"},
    )
