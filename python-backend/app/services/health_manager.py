"""Device health monitor — heartbeat, battery, proxy checks + auto-heal."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.api._hub import hub
from app.database import SessionLocal
from app.models.device import Device
from app.services.antidetect import proxy_manager

HEARTBEAT_TIMEOUT = timedelta(seconds=90)
LOW_BATTERY = 15


class HealthManager:
    def __init__(self, *, poll_interval: float = 30.0) -> None:
        self._poll = poll_interval
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._cooldown: dict[str, datetime] = {}
        self._warmup_coefficient = 0.0

    @property
    def warmup_coefficient(self) -> float:
        return self._warmup_coefficient

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self.monitor_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def monitor_loop(self) -> None:
        while self._running:
            try:
                await self.tick()
            except Exception:
                pass
            await asyncio.sleep(self._poll)

    async def tick(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        healed: list[str] = []

        async with SessionLocal() as session:
            devices = list((await session.execute(select(Device))).scalars().all())
            active = 0
            for device in devices:
                state = self._assess(device, now)
                if state == "ok":
                    active += 1
                    continue
                if not self._can_heal(device.id, now):
                    continue
                await self._heal(session, device, state)
                healed.append(device.id)

            self._warmup_coefficient = round(min(1.0, active / 50.0), 4)
            await session.commit()

        await hub.broadcast(
            "warmup",
            {
                "coefficient": self._warmup_coefficient,
                "active_devices": active,
                "total": len(devices) if devices else 0,
                "healed": healed,
            },
        )
        return {
            "active": active,
            "healed": healed,
            "warmup_coefficient": self._warmup_coefficient,
        }

    @staticmethod
    def _assess(device: Device, now: datetime) -> str:
        heartbeat = device.last_heartbeat
        if heartbeat is None or (now - _as_aware(heartbeat)) > HEARTBEAT_TIMEOUT:
            return "stale_heartbeat"
        if device.battery_level is not None and device.battery_level < LOW_BATTERY:
            return "low_battery"
        if device.status == "error":
            return "error"
        return "ok"

    def _can_heal(self, device_id: str, now: datetime) -> bool:
        cooldown_until = self._cooldown.get(device_id)
        return cooldown_until is None or cooldown_until <= now

    async def _heal(self, session, device: Device, state: str) -> None:
        now = datetime.now(timezone.utc)
        if state == "stale_heartbeat":
            device.status = "reconnecting"
        elif state == "error":
            device.status = "restarting"
            try:
                await proxy_manager.rotate(device.id)
            except Exception:
                pass
        elif state == "low_battery":
            device.status = "cooldown"
            self._cooldown[device.id] = now + timedelta(minutes=20)
        else:
            device.status = "recovering"

        await hub.broadcast(
            "devices",
            {"event": "heal", "device_id": device.id, "state": state, "status": device.status},
        )

    def update_warmup_coefficient(self, active_devices: int) -> float:
        self._warmup_coefficient = round(min(1.0, active_devices / 50.0), 4)
        return self._warmup_coefficient


def _as_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


health_manager = HealthManager()
