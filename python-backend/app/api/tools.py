"""Endpoints for managing bundled CLI tools (adb, libimobiledevice)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import tools as tools_svc

router = APIRouter(prefix="/tools", tags=["tools"])


class InstallPayload(BaseModel):
    target: str = "all"  # "all" | "adb" | "ios"


@router.get("/status")
async def get_status() -> dict:
    return tools_svc.status()


@router.post("/install")
async def install(payload: InstallPayload) -> dict:
    return await tools_svc.install(payload.target)
