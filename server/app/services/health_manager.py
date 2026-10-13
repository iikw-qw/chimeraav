"""
Health Manager: мониторинг устройств, обнаружение сбоев, автовосстановление.
Зависит от: database, redis_client, notification_service, models
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.device import Device
from app.services.redis_client import redis_client

logger = structlog.get_logger()

HEARTBEAT_TIMEOUT = 15  # Секунды без heartbeat → устройство offline
RECOVERY_CASCADE = ["restart_app", "reboot_device", "escalate"]


class HealthManager:
    def __init__(self):
        self._running = False
        self._device_last_seen: Dict[str, float] = {}

    async def start(self):
        """Запуск цикла мониторинга"""
        self._running = True
        logger.info("health_manager.started")
        asyncio.create_task(self._monitor_loop())
        asyncio.create_task(self._warmup_coefficient_loop())

    async def stop(self):
        """Остановка мониторинга"""
        self._running = False
        logger.info("health_manager.stopped")

    async def _monitor_loop(self):
        """Основной цикл мониторинга (каждые 10 сек)"""
        while self._running:
            try:
                await self._check_all_devices()
            except Exception as e:
                logger.error("health_manager.monitor_error", error=str(e))
            await asyncio.sleep(10)

    async def _warmup_coefficient_loop(self):
        """Обновление warmup_coefficient каждые 60 сек"""
        while self._running:
            try:
                await self._update_warmup_coefficient()
            except Exception as e:
                logger.error("health_manager.warmup_error", error=str(e))
            await asyncio.sleep(60)

    async def _check_all_devices(self):
        """Проверка всех устройств"""
        async with async_session_factory() as db:
            result = await db.execute(
                select(Device).where(Device.status.in_(["online", "busy"]))
            )
            devices = result.scalars().all()

            for device in devices:
                device_id = str(device.id)
                last_seen = self._device_last_seen.get(device_id, 0)
                now = time.time()

                # Проверяем heartbeat
                heartbeat = await redis_client.get_cache(f"heartbeat:{device_id}")
                if heartbeat:
                    self._device_last_seen[device_id] = now
                    continue

                # Нет heartbeat — проверяем таймаут
                if now - last_seen > HEARTBEAT_TIMEOUT and last_seen > 0:
                    logger.warning("device.heartbeat_timeout", device_id=device_id, seconds=int(now - last_seen))
                    await self._handle_device_failure(db, device)

            await db.commit()

    async def _handle_device_failure(self, db: AsyncSession, device: Device):
        """Обработка сбоя устройства (каскадное восстановление)"""
        device_id = str(device.id)

        # Получаем текущий шаг восстановления
        recovery_step = await redis_client.get_cache(f"recovery:{device_id}") or 0
        recovery_step = int(recovery_step)

        if recovery_step >= len(RECOVERY_CASCADE):
            logger.error("device.recovery_exhausted", device_id=device_id)
            device.status = "error"
            # Уведомление оператору
            await redis_client.publish("chimera:telegram_notifications", {
                "type": "device_error",
                "device_id": device_id,
                "device_name": device.name,
                "message": f"Устройство {device.name} не отвечает. Требуется ручное вмешательство.",
            })
            return

        action = RECOVERY_CASCADE[recovery_step]
        logger.info("device.recovery_attempt", device_id=device_id, action=action, step=recovery_step)

        if action == "restart_app":
            await redis_client.publish(f"device:{device_id}:commands", {"type": "restart_app"})
        elif action == "reboot_device":
            await redis_client.publish(f"device:{device_id}:commands", {"type": "reboot"})
        elif action == "escalate":
            device.status = "error"
            await redis_client.publish("chimera:telegram_notifications", {
                "type": "device_error",
                "device_id": device_id,
                "device_name": device.name,
                "message": f"Устройство {device.name}: автовосстановление не помогло.",
            })

        await redis_client.set_cache(f"recovery:{device_id}", recovery_step + 1, ttl=300)

    async def _update_warmup_coefficient(self):
        """Обновление адаптивного коэффициента прогрева"""
        async with async_session_factory() as db:
            result = await db.execute(
                select(Device).where(Device.status == "online")
            )
            active_count = len(result.scalars().all())

        coefficient = min(1.0, active_count / 50)
        await redis_client.set_warmup_coefficient(coefficient)
        logger.debug("warmup_coefficient.updated", value=coefficient, active_devices=active_count)

    async def register_heartbeat(self, device_id: str, metadata: Dict[str, Any]):
        """Регистрация heartbeat от устройства"""
        self._device_last_seen[device_id] = time.time()
        await redis_client.set_cache(f"heartbeat:{device_id}", metadata, ttl=HEARTBEAT_TIMEOUT * 2)

        # Обновляем статус устройства в БД
        async with async_session_factory() as db:
            await db.execute(
                update(Device)
                .where(Device.id == UUID(device_id))
                .values(
                    status="online",
                    battery_level=metadata.get("battery"),
                    temperature=metadata.get("temperature"),
                    external_ip=metadata.get("external_ip"),
                    last_seen_at=datetime.utcnow(),
                )
            )
            await db.commit()

        # Сбрасываем шаг восстановления
        await redis_client.delete_cache(f"recovery:{device_id}")

    async def run_calibration(self, device_id: str) -> Dict[str, Any]:
        """Self-Test (калибровка) при подключении нового устройства"""
        checks = {
            "connectivity": False,
            "battery_ok": False,
            "apps_installed": False,
            "proxy_ok": False,
        }

        # Проверка связи
        heartbeat = await redis_client.get_cache(f"heartbeat:{device_id}")
        checks["connectivity"] = heartbeat is not None

        if heartbeat:
            checks["battery_ok"] = (heartbeat.get("battery", 0) or 0) > 20

        # Проверка прокси
        proxy = await redis_client.hget("chimera:device_proxies", device_id)
        checks["proxy_ok"] = proxy is not None

        all_ok = all(checks.values())
        logger.info("calibration.complete", device_id=device_id, checks=checks, passed=all_ok)

        return {"device_id": device_id, "checks": checks, "passed": all_ok}


health_manager = HealthManager()
