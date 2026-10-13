from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.post import Post
from app.models.task import Task

from ._deps import get_or_404, get_session

router = APIRouter(prefix="/posts", tags=["posts"])


class GeneratePayload(BaseModel):
    account_id: str
    platform: str
    dataset_id: str | None = None
    caption_hint: str | None = None
    photo_count: int = 3
    mix_strategy: str = "smart"
    media_kind: str = "photo"
    clean_metadata: bool = True


class PostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    account_id: str
    platform: str
    photos: list[Any] | None = None
    caption: str | None = None
    video_url: str | None = None
    sipr_dataset_id: str | None = None
    metadata_cleaned: bool
    published_at: datetime | None = None
    engagement_metrics: dict[str, Any] | None = None


@router.post("/generate", status_code=201)
async def generate_post(
    payload: GeneratePayload,
    background: BackgroundTasks,
) -> dict:
    from app.services.post_generator import post_generator

    if not payload.dataset_id:
        raise HTTPException(status_code=400, detail="dataset_id is required for generation")

    strategy = payload.mix_strategy if payload.mix_strategy in {
        "wear", "interleave", "random_offset", "stride", "cross", "smart"
    } else "smart"
    media_kind = payload.media_kind if payload.media_kind in {"photo", "video"} else "photo"

    result = await post_generator.generate(
        payload.account_id,
        payload.dataset_id,
        payload.platform,
        photo_count=payload.photo_count,
        clean_metadata=payload.clean_metadata,
        mix_strategy=strategy,  # type: ignore[arg-type]
        media_kind=media_kind,  # type: ignore[arg-type]
    )
    background.add_task(_notify_post_queued, result["post_id"])
    return result


async def _notify_post_queued(post_id: str) -> None:
    from ._hub import hub

    await hub.broadcast("tasks", {"event": "post_generation_queued", "post_id": post_id})


@router.get("/schedule")
async def post_schedule(
    session: Annotated[AsyncSession, Depends(get_session)],
    days: int = 7,
) -> list[dict]:
    horizon = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=days)
    stmt = (
        select(Task)
        .where(Task.task_type == "publish_post", Task.status == "pending")
        .order_by(Task.scheduled_at.asc().nullslast())
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return [
        {
            "task_id": t.id,
            "account_id": t.account_id,
            "scheduled_at": t.scheduled_at.isoformat() if t.scheduled_at else None,
            "payload": t.payload,
        }
        for t in rows
        if not t.scheduled_at or t.scheduled_at <= horizon
    ]


class PublishPayload(BaseModel):
    schedule_at: datetime | None = None


@router.post("/{post_id}/publish")
async def publish_post(
    post_id: str,
    payload: PublishPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    post = await get_or_404(session, Post, post_id)
    account = await session.get(Account, post.account_id)
    if account is None or not account.device_id:
        raise HTTPException(
            status_code=400,
            detail="post account has no associated device",
        )
    task = Task(
        device_id=account.device_id,
        account_id=post.account_id,
        task_type="publish_post",
        status="pending",
        priority=3,
        scheduled_at=payload.schedule_at,
        payload={"post_id": post.id, "platform": post.platform},
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return {
        "task_id": task.id,
        "post_id": post.id,
        "scheduled_at": task.scheduled_at.isoformat() if task.scheduled_at else None,
        "status": "scheduled",
    }
