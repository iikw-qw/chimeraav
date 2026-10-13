"""Aggregate router — mounted at /api by the FastAPI app."""

from __future__ import annotations

from fastapi import APIRouter

from . import (
    accounts,
    auth,
    autoclicker,
    batch,
    captions,
    comments,
    content,
    dashboard,
    datasets,
    devices,
    incoming_messages,
    ios_automation,
    logs,
    media,
    metadata,
    posts,
    proxies,
    registration,
    settings,
    streaming,
    tasks,
    telegram,
    templates,
    tools,
    users_pool,
    websocket,
)

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router)
api_router.include_router(devices.router)
api_router.include_router(accounts.router)
api_router.include_router(comments.router)
api_router.include_router(incoming_messages.router)
api_router.include_router(templates.router)
api_router.include_router(datasets.router)
api_router.include_router(posts.router)
api_router.include_router(tasks.router)
api_router.include_router(proxies.router)
api_router.include_router(settings.router)
api_router.include_router(metadata.router)
api_router.include_router(dashboard.router)
api_router.include_router(telegram.router)
api_router.include_router(batch.router)
api_router.include_router(tools.router)
api_router.include_router(users_pool.router)
api_router.include_router(registration.router)
api_router.include_router(streaming.router)
api_router.include_router(captions.router)
api_router.include_router(content.router)
api_router.include_router(autoclicker.router)
api_router.include_router(media.router)
api_router.include_router(logs.router)
api_router.include_router(ios_automation.router)
api_router.include_router(websocket.router)
