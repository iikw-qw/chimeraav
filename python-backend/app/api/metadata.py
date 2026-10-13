from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.metadata_clean import clean_image_file
from app.models.metadata_cleaning import MetadataCleaning

from ._deps import get_session

router = APIRouter(prefix="/metadata", tags=["metadata"])


class CleanPayload(BaseModel):
    file_path: str


class CleanResponse(BaseModel):
    file_path: str
    original_hash: str
    cleaned_hash: str
    exif_removed: bool
    gps_removed: bool
    digital_fingerprint_modified: bool


@router.post("/clean", response_model=CleanResponse)
async def clean_one(
    payload: CleanPayload, session: Annotated[AsyncSession, Depends(get_session)]
) -> CleanResponse:
    p = Path(payload.file_path)
    if not p.exists() or not p.is_file():
        raise HTTPException(404, "File not found")
    try:
        result = clean_image_file(p)
    except Exception as exc:
        raise HTTPException(500, f"Cleaning failed: {exc}") from exc

    record = MetadataCleaning(
        file_path=result.file_path,
        original_hash=result.original_hash,
        cleaned_hash=result.cleaned_hash,
        exif_removed=result.exif_removed,
        gps_removed=result.gps_removed,
        digital_fingerprint_modified=result.digital_fingerprint_modified,
        cleaned_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(record)
    await session.commit()
    return CleanResponse(**result.__dict__)


class CleanBatchPayload(BaseModel):
    file_paths: list[str]


@router.post("/clean-batch")
async def clean_batch(payload: CleanBatchPayload, background: BackgroundTasks) -> dict:
    valid = [p for p in payload.file_paths if Path(p).is_file()]
    background.add_task(_clean_batch_job, valid)
    return {"queued": len(valid), "skipped": len(payload.file_paths) - len(valid)}


async def _clean_batch_job(file_paths: list[str]) -> None:
    from app.database import SessionLocal

    async with SessionLocal() as session:
        for fp in file_paths:
            try:
                result = clean_image_file(Path(fp))
            except Exception:
                continue
            session.add(
                MetadataCleaning(
                    file_path=result.file_path,
                    original_hash=result.original_hash,
                    cleaned_hash=result.cleaned_hash,
                    exif_removed=result.exif_removed,
                    gps_removed=result.gps_removed,
                    digital_fingerprint_modified=result.digital_fingerprint_modified,
                    cleaned_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
            )
        await session.commit()
