"""APScheduler lifecycle wrappers."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _device_scan_tick() -> None:
    from app.api._hub import hub
    from app.api.devices import perform_scan
    from app.database import SessionLocal

    async with SessionLocal() as session:
        try:
            devices, *_ = await perform_scan(session)
        except Exception as err:
            log.debug("device scan tick failed: %s", err)
            return
    await hub.broadcast(
        "devices",
        {"event": "scan", "count": len(devices)},
    )


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
        _scheduler.add_job(
            _device_scan_tick,
            "interval",
            seconds=8,
            id="device-scan",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        _scheduler.start()
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler
