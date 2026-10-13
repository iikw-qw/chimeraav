"""
API управления постами и датасетами.
Зависит от: models/post, models/dataset, schemas/post, deps
"""

import os
import uuid as uuid_mod
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.post import Post
from app.models.dataset import Dataset
from app.models.user import User
from app.schemas.post import PostCreate, PostUpdate, PostResponse, DatasetCreate, DatasetResponse
from app.api.deps import get_current_user

router = APIRouter()

UPLOAD_DIR = "/app/uploads"


@router.get("", response_model=list[PostResponse])
async def list_posts(
    status: Optional[str] = None,
    platform: Optional[str] = None,
    account_id: Optional[UUID] = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Post).where(Post.user_id == current_user.id)
    if status:
        query = query.where(Post.status == status)
    if platform:
        query = query.where(Post.platform == platform)
    if account_id:
        query = query.where(Post.account_id == account_id)
    query = query.order_by(Post.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return [PostResponse.model_validate(p) for p in result.scalars().all()]


@router.post("", response_model=PostResponse, status_code=201)
async def create_post(
    data: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    post = Post(user_id=current_user.id, **data.model_dump())
    if data.scheduled_at:
        post.status = "scheduled"
    db.add(post)
    await db.flush()
    await db.refresh(post)
    return PostResponse.model_validate(post)


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return PostResponse.model_validate(post)


@router.put("/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: UUID,
    data: PostUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(post, field, value)

    await db.flush()
    await db.refresh(post)
    return PostResponse.model_validate(post)


@router.delete("/{post_id}")
async def delete_post(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    await db.delete(post)
    return {"message": "Post deleted"}


# ═══ Datasets ═══

@router.get("/datasets/list", response_model=list[DatasetResponse])
async def list_datasets(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Dataset).where(Dataset.user_id == current_user.id).order_by(Dataset.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return [DatasetResponse.model_validate(d) for d in result.scalars().all()]


@router.post("/datasets", response_model=DatasetResponse, status_code=201)
async def create_dataset(
    data: DatasetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dataset = Dataset(
        user_id=current_user.id,
        name=data.name,
        photos=data.photos,
        total_photos=len(data.photos),
    )
    db.add(dataset)
    await db.flush()
    await db.refresh(dataset)
    return DatasetResponse.model_validate(dataset)


@router.post("/datasets/{dataset_id}/upload")
async def upload_photos(
    dataset_id: UUID,
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    uploaded = []
    for file in files:
        ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
        filename = f"{uuid_mod.uuid4()}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)
        uploaded.append(filename)

    current_photos = dataset.photos or []
    dataset.photos = current_photos + uploaded
    dataset.total_photos = len(dataset.photos)

    await db.flush()
    return {"uploaded": len(uploaded), "total": dataset.total_photos, "files": uploaded}
