"""Chimera FastAPI sidecar entry point."""

import asyncio
import logging
import socket
import subprocess
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.router import api_router
from app.api.auth_v1 import router as auth_v1_router
from app.api.stream_v1 import router as stream_v1_router, ws_router as stream_ws_router
from app.api.services_v1 import router as services_v1_router, ws_router as services_ws_router
from app.config import settings
from app.database import init_db
from app.scheduler import start_scheduler, stop_scheduler
from app.seed import seed_templates
from app.services.antidetect import set_behavior_profile, set_captcha_key
from utils.ws_manager import ws_manager

from sqlalchemy import select
from app.database import SessionLocal
from app.models.app_settings import AppSettings

logger = logging.getLogger(__name__)


async def _hydrate_runtime_settings() -> None:
    async with SessionLocal() as session:
        rows = list(
            (
                await session.execute(
                    select(AppSettings).where(
                        AppSettings.key.in_(["human_behavior_profile", "twocaptcha_api_key"])
                    )
                )
            )
            .scalars()
            .all()
        )
    for row in rows:
        if row.key == "human_behavior_profile" and row.value in ("calm", "normal", "fast"):
            set_behavior_profile(row.value)
        elif row.key == "twocaptcha_api_key" and isinstance(row.value, str):
            set_captcha_key(row.value)


async def device_monitor() -> None:
    known_serials: set[str] = set()
    while True:
        try:
            from utils.adb_utils import adb_devices, is_adb_available
            if not is_adb_available():
                await asyncio.sleep(10)
                continue
            devs = adb_devices()
            current = {d["serial"] for d in devs if d["state"] == "device"}

            changed = (current - known_serials) or (known_serials - current)

            if changed:
                try:
                    from app.api.devices import perform_scan
                    async with SessionLocal() as session:
                        await perform_scan(session)
                except Exception as exc:
                    logger.error("Device scan during monitor failed: %s", exc)

            for serial in current - known_serials:
                logger.info("New device detected: %s", serial)
                try:
                    from services.platform_detector import detect_and_save_platforms
                    await detect_and_save_platforms(serial)
                except Exception:
                    pass
                await ws_manager.broadcast("devices", {
                    "event": "device_connected",
                    "serial": serial,
                })

            for serial in known_serials - current:
                logger.info("Device disconnected: %s", serial)
                await ws_manager.broadcast("devices", {
                    "event": "device_disconnected",
                    "serial": serial,
                })

            known_serials = current
        except Exception as exc:
            logger.error("Device monitor error: %s", exc)

        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    await seed_templates()
    await _hydrate_runtime_settings()
    start_scheduler()
    from services.device_heartbeat import heartbeat_loop
    monitor_task = asyncio.create_task(device_monitor())
    heartbeat_task = asyncio.create_task(heartbeat_loop())
    try:
        yield
    finally:
        monitor_task.cancel()
        heartbeat_task.cancel()
        stop_scheduler()


app = FastAPI(
    title="Chimera API",
    version="5.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(api_router)
app.include_router(auth_v1_router, prefix="/api")
app.include_router(stream_v1_router, prefix="/api")
app.include_router(services_v1_router, prefix="/api")
app.include_router(stream_ws_router)
app.include_router(services_ws_router)


@app.get("/health")
async def health() -> dict:
    from utils.adb_utils import is_adb_available
    return {"status": "ok", "version": "9.0.0", "adb_available": is_adb_available()}




def _loopback_sockets(port: int) -> list[socket.socket]:
    socks: list[socket.socket] = []
    for family, addr in (
        (socket.AF_INET, ("127.0.0.1", port)),
        (socket.AF_INET6, ("::1", port, 0, 0)),
    ):
        try:
            s = socket.socket(family, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if family == socket.AF_INET6:
                try:
                    s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                except (AttributeError, OSError):
                    pass
            s.bind(addr)
            s.listen(128)
            s.setblocking(False)
            socks.append(s)
        except OSError:
            pass
    if not socks:
        raise RuntimeError(f"Could not bind any loopback socket on port {port}")
    return socks


if __name__ == "__main__":
    socks = _loopback_sockets(settings.port)
    config = uvicorn.Config(
        "main:app",
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run(sockets=socks)
