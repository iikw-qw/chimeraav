"""Media gallery API — upload, list, delete, analyze quality."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media_file import MediaFile
from app.services.quality_analyzer import QualityAnalyzer

from ._deps import get_or_404, get_session

router = APIRouter(prefix="/media", tags=["media"])

_MEDIA_DIR = Path(os.environ.get("CHIMERA_MEDIA_DIR", ""))
if not _MEDIA_DIR.is_absolute():
    _MEDIA_DIR = Path(__file__).resolve().parent.parent.parent / "media_files"
_MEDIA_DIR.mkdir(parents=True, exist_ok=True)


class MediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    file_path: str
    file_type: str
    file_size: int | None
    width: int | None
    height: int | None
    tags: str
    quality_score: float | None
    is_unique: bool
    created_at: str


@router.get("")
async def list_media(
    session: Annotated[AsyncSession, Depends(get_session)],
    file_type: str | None = Query(None),
    tag: str | None = Query(None),
    min_quality: float | None = Query(None),
    limit: int = Query(200, le=1000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    stmt = select(MediaFile).order_by(MediaFile.created_at.desc())
    if file_type:
        stmt = stmt.where(MediaFile.file_type == file_type)
    if min_quality is not None:
        stmt = stmt.where(MediaFile.quality_score >= min_quality)
    stmt = stmt.offset(offset).limit(limit)
    rows = list((await session.execute(stmt)).scalars().all())

    result = []
    for r in rows:
        d = {
            "id": r.id, "filename": r.filename, "file_path": r.file_path,
            "file_type": r.file_type, "file_size": r.file_size,
            "width": r.width, "height": r.height,
            "tags": json.loads(r.tags) if r.tags else [],
            "quality_score": r.quality_score, "is_unique": r.is_unique,
            "created_at": str(r.created_at),
        }
        if tag and tag not in d["tags"]:
            continue
        result.append(d)
    return result


@router.post("/upload")
async def upload_media(
    file: UploadFile,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    if not file.filename:
        raise HTTPException(400, "No filename")

    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "").lower()
    photo_exts = {"jpg", "jpeg", "png", "webp", "bmp", "gif"}
    video_exts = {"mp4", "mov", "avi", "mkv", "webm"}
    if ext in photo_exts:
        file_type = "photo"
    elif ext in video_exts:
        file_type = "video"
    else:
        raise HTTPException(400, f"Unsupported format: .{ext}")

    from app.models._common import new_uuid
    file_id = new_uuid()
    dest = _MEDIA_DIR / f"{file_id}.{ext}"

    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)

    width, height = None, None
    quality_score = None
    if file_type == "photo":
        try:
            from PIL import Image
            img = Image.open(dest)
            width, height = img.size
            img.close()
        except Exception:
            pass
        try:
            qa = QualityAnalyzer()
            scores = qa.analyze(str(dest))
            quality_score = scores.get("total")
        except Exception:
            pass

    media = MediaFile(
        id=file_id,
        filename=file.filename,
        file_path=str(dest),
        file_type=file_type,
        file_size=len(content),
        width=width,
        height=height,
        quality_score=quality_score,
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)

    return {
        "id": media.id, "filename": media.filename,
        "file_type": media.file_type, "file_size": media.file_size,
        "width": media.width, "height": media.height,
        "quality_score": media.quality_score,
    }


@router.delete("/{media_id}")
async def delete_media(
    media_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    media = await get_or_404(session, MediaFile, media_id)
    try:
        os.remove(media.file_path)
    except FileNotFoundError:
        pass
    await session.delete(media)
    await session.commit()
    return {"ok": True}


@router.post("/batch-delete")
async def batch_delete(
    ids: list[str],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    deleted = 0
    for mid in ids:
        media = await session.get(MediaFile, mid)
        if media:
            try:
                os.remove(media.file_path)
            except FileNotFoundError:
                pass
            await session.delete(media)
            deleted += 1
    await session.commit()
    return {"ok": True, "deleted": deleted}


@router.post("/{media_id}/uniqueize")
async def uniqueize_media(
    media_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    media = await get_or_404(session, MediaFile, media_id)
    from app.services.content_uniqueizer import ContentUniqueizer
    uniq = ContentUniqueizer()
    out_path = media.file_path.rsplit(".", 1)[0] + "_unique." + media.file_path.rsplit(".", 1)[-1]

    if media.file_type == "photo":
        result = uniq.uniqueize_photo(media.file_path, out_path)
    elif media.file_type == "video":
        result = uniq.uniqueize_video(media.file_path, out_path)
    else:
        raise HTTPException(400, "Unknown file type")

    if os.path.exists(out_path):
        shutil.move(out_path, media.file_path)
        media.is_unique = True
        await session.commit()

    return result


@router.post("/{media_id}/analyze")
async def analyze_quality(
    media_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    media = await get_or_404(session, MediaFile, media_id)
    if media.file_type != "photo":
        raise HTTPException(400, "Quality analysis only for photos")
    qa = QualityAnalyzer()
    scores = qa.analyze(media.file_path)
    media.quality_score = scores.get("total")
    await session.commit()
    return scores
