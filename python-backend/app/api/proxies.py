from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.proxy import Proxy

from ._deps import apply_update, get_or_404, get_session

router = APIRouter(prefix="/proxies", tags=["proxies"])


class ProxyBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    address: str
    port: int
    username: str | None = None
    password: str | None = None
    protocol: str = "http"
    country: str | None = None
    is_active: bool = True


class ProxyCreate(ProxyBase):
    pass


class ProxyUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    address: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    protocol: str | None = None
    country: str | None = None
    is_active: bool | None = None


class ProxyRead(ProxyBase):
    id: str
    leak_check_passed: bool
    last_checked: datetime | None = None


@router.get("", response_model=list[ProxyRead])
async def list_proxies(
    session: Annotated[AsyncSession, Depends(get_session)],
    active_only: bool = False,
) -> list[Proxy]:
    stmt = select(Proxy)
    if active_only:
        stmt = stmt.where(Proxy.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


@router.post("", response_model=ProxyRead, status_code=201)
async def create_proxy(
    payload: ProxyCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> Proxy:
    proxy = Proxy(**payload.model_dump())
    session.add(proxy)
    await session.commit()
    await session.refresh(proxy)
    return proxy


@router.get("/{proxy_id}", response_model=ProxyRead)
async def get_proxy(
    proxy_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> Proxy:
    return await get_or_404(session, Proxy, proxy_id)


@router.put("/{proxy_id}", response_model=ProxyRead)
async def update_proxy(
    proxy_id: str,
    payload: ProxyUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Proxy:
    proxy = await get_or_404(session, Proxy, proxy_id)
    apply_update(proxy, payload)
    await session.commit()
    await session.refresh(proxy)
    return proxy


@router.delete("/{proxy_id}", status_code=204)
async def delete_proxy(
    proxy_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> Response:
    proxy = await get_or_404(session, Proxy, proxy_id)
    await session.delete(proxy)
    await session.commit()
    return Response(status_code=204)


@router.post("/check-all")
async def check_all_proxies(
    background: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    proxies = list((await session.execute(select(Proxy))).scalars().all())
    background.add_task(_run_proxy_checks, [p.id for p in proxies])
    return {"queued": len(proxies), "status": "scheduled"}


async def _run_proxy_checks(proxy_ids: list[str]) -> None:
    from app.database import SessionLocal

    async with SessionLocal() as session:
        for pid in proxy_ids:
            proxy = await session.get(Proxy, pid)
            if proxy is None:
                continue
            ok = await _check_proxy(proxy)
            proxy.leak_check_passed = ok
            proxy.last_checked = datetime.now(timezone.utc).replace(tzinfo=None)
            await session.commit()


async def _check_proxy(proxy: Proxy) -> bool:
    auth = ""
    if proxy.username and proxy.password:
        auth = f"{proxy.username}:{proxy.password}@"
    url = f"{proxy.protocol}://{auth}{proxy.address}:{proxy.port}"
    try:
        async with httpx.AsyncClient(proxy=url, timeout=8.0) as client:
            r = await client.get("https://api.ipify.org?format=json")
            return r.status_code == 200
    except Exception:
        return False
