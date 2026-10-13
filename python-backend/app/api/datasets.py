from __future__ import annotations

import mimetypes
import shutil
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv"}

from app.config import settings
from app.models.dataset import Dataset
from app.models.device import Device

from ._deps import apply_update, get_or_404, get_session

router = APIRouter(prefix="/datasets", tags=["datasets"])


class DatasetBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    path: str
    photo_count: int = 0
    video_count: int = 0
    wear_map: dict[str, Any] | None = None
    linked_device_id: str | None = None
    metadata_cleaned: bool = False


class DatasetCreate(DatasetBase):
    pass


class DatasetUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str | None = None
    path: str | None = None
    photo_count: int | None = None
    video_count: int | None = None
    wear_map: dict[str, Any] | None = None
    linked_device_id: str | None = None
    metadata_cleaned: bool | None = None


class DatasetRead(DatasetBase):
    id: str
    created_at: datetime


@router.get("", response_model=list[DatasetRead])
async def list_datasets(
    session: Annotated[AsyncSession, Depends(get_session)],
    device_id: str | None = None,
) -> list[Dataset]:
    stmt = select(Dataset)
    if device_id:
        stmt = stmt.where(Dataset.linked_device_id == device_id)
    stmt = stmt.order_by(Dataset.created_at.desc())
    return list((await session.execute(stmt)).scalars().all())


@router.post("", response_model=DatasetRead, status_code=201)
async def create_dataset(
    payload: DatasetCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> Dataset:
    ds = Dataset(**payload.model_dump())
    session.add(ds)
    await session.commit()
    await session.refresh(ds)
    return ds


@router.get("/{dataset_id}", response_model=DatasetRead)
async def get_dataset(
    dataset_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> Dataset:
    return await get_or_404(session, Dataset, dataset_id)


@router.put("/{dataset_id}", response_model=DatasetRead)
async def update_dataset(
    dataset_id: str,
    payload: DatasetUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Dataset:
    ds = await get_or_404(session, Dataset, dataset_id)
    apply_update(ds, payload)
    await session.commit()
    await session.refresh(ds)
    return ds


@router.delete("/{dataset_id}", status_code=204)
async def delete_dataset(
    dataset_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> Response:
    ds = await get_or_404(session, Dataset, dataset_id)
    await session.delete(ds)
    await session.commit()
    return Response(status_code=204)


@router.post("/{dataset_id}/link/{device_id}", response_model=DatasetRead)
async def link_dataset(
    dataset_id: str,
    device_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Dataset:
    ds = await get_or_404(session, Dataset, dataset_id)
    await get_or_404(session, Device, device_id)
    ds.linked_device_id = device_id
    await session.commit()
    await session.refresh(ds)
    return ds


@router.delete("/{dataset_id}/unlink", response_model=DatasetRead)
async def unlink_dataset(
    dataset_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> Dataset:
    ds = await get_or_404(session, Dataset, dataset_id)
    ds.linked_device_id = None
    await session.commit()
    await session.refresh(ds)
    return ds


@router.post("/{dataset_id}/clean-metadata")
async def clean_dataset_metadata(
    dataset_id: str,
    background: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    ds = await get_or_404(session, Dataset, dataset_id)
    background.add_task(_clean_dataset_files, ds.id, ds.path)
    return {"dataset_id": ds.id, "status": "scheduled"}


async def _clean_dataset_files(dataset_id: str, path: str) -> None:
    from app.database import SessionLocal
    from app.metadata_clean import clean_image_file

    target = Path(path)
    if not target.exists():
        return
    cleaned = 0
    for file in target.rglob("*"):
        if file.is_file() and file.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            try:
                clean_image_file(file)
                cleaned += 1
            except Exception:
                continue
    async with SessionLocal() as session:
        ds = await session.get(Dataset, dataset_id)
        if ds:
            ds.metadata_cleaned = True
            await session.commit()


@router.get("/{dataset_id}/files")
async def list_dataset_files(
    dataset_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 200,
) -> dict:
    ds = await get_or_404(session, Dataset, dataset_id)
    root = Path(ds.path)
    photos: list[dict] = []
    videos: list[dict] = []
    if root.exists():
        for file in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if not file.is_file():
                continue
            ext = file.suffix.lower()
            entry = {"name": file.name, "size": file.stat().st_size}
            if ext in PHOTO_EXTS:
                photos.append(entry)
            elif ext in VIDEO_EXTS:
                videos.append(entry)
            if len(photos) + len(videos) >= limit:
                break
    return {"dataset_id": ds.id, "photos": photos, "videos": videos}


@router.get("/{dataset_id}/file/{filename}")
async def get_dataset_file(
    dataset_id: str,
    filename: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FileResponse:
    ds = await get_or_404(session, Dataset, dataset_id)
    root = Path(ds.path).resolve()
    target = (root / filename).resolve()
    # prevent path traversal
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(400, "invalid filename")
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "file not found")
    mime, _ = mimetypes.guess_type(target.name)
    return FileResponse(
        str(target),
        media_type=mime or "application/octet-stream",
        headers={"Cache-Control": "max-age=60"},
    )


@router.post("/upload", response_model=DatasetRead, status_code=201)
async def upload_dataset(
    name: Annotated[str, Form()],
    files: Annotated[list[UploadFile], File()],
    session: Annotated[AsyncSession, Depends(get_session)],
    linked_device_id: Annotated[str | None, Form()] = None,
) -> Dataset:
    if not files:
        raise HTTPException(400, "No files uploaded")

    target_dir = Path(settings.data_dir) / "datasets" / name
    target_dir.mkdir(parents=True, exist_ok=True)

    photos = 0
    videos = 0

    for upload in files:
        filename = Path(upload.filename or "file").name
        dest = target_dir / filename
        with dest.open("wb") as out:
            shutil.copyfileobj(upload.file, out)
        ext = dest.suffix.lower()
        if ext in PHOTO_EXTS:
            photos += 1
        elif ext in VIDEO_EXTS:
            videos += 1

    ds = Dataset(
        name=name,
        path=str(target_dir),
        photo_count=photos,
        video_count=videos,
        linked_device_id=linked_device_id,
    )
    session.add(ds)
    await session.commit()
    await session.refresh(ds)
    return ds
