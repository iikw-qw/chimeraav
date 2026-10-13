"""
Сервис управления устройствами: обнаружение, статус, команды, обновление инфо.
Зависит от: config, database, redis_client, models/device
"""

import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.device import Device
from app.services.redis_client import redis_client

logger = structlog.get_logger()

# Redis key prefixes
DEVICE_STATUS_KEY = "chimera:device:status:{device_id}"
DEVICE_INFO_KEY = "chimera:device:info:{device_id}"
DEVICE_COMMAND_CHANNEL = "device:{device_id}:commands"
DEVICE_HEARTBEAT_KEY = "chimera:device:heartbeat:{device_id}"

# Таймаут после которого устройство считается офлайн (секунды)
HEARTBEAT_TIMEOUT_SECONDS = 120

# ADB default port
ADB_DEFAULT_PORT = 5555


class DeviceManager:
    """
    Управление устройствами: обнаружение по сети, отслеживание статуса,
    отправка команд через Redis pub/sub, обновление информации.
    """

    def __init__(self):
        self._monitoring_task: Optional[asyncio.Task] = None
        self._running = False

    # ═══════════════════════════════════════════════════════════
    # Обнаружение устройств в сети через ADB
    # ═══════════════════════════════════════════════════════════

    async def discover_devices(
        self,
        subnet: str = "192.168.1",
        port: int = ADB_DEFAULT_PORT,
        timeout: float = 2.0,
    ) -> List[Dict[str, Any]]:
        """
        Сканирование подсети на наличие ADB-устройств.
        Проверяем каждый IP в подсети на открытый ADB-порт.
        """
        discovered: List[Dict[str, Any]] = []
        tasks = []

        for i in range(1, 255):
            ip = f"{subnet}.{i}"
            tasks.append(self._probe_adb_host(ip, port, timeout))

        # Параллельный сканирование всех адресов в подсети
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, dict):
                discovered.append(result)

        logger.info(
            "device_discovery.complete",
            subnet=subnet,
            found=len(discovered),
        )
        return discovered

    async def _probe_adb_host(
        self, ip: str, port: int, timeout: float
    ) -> Optional[Dict[str, Any]]:
        """
        Проверка конкретного хоста на наличие ADB-демона.
        Подключаемся к TCP-порту и проверяем ADB handshake.
        """
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=timeout,
            )
            # ADB-демон отвечает на подключение — устройство найдено
            writer.close()
            await writer.wait_closed()

            logger.debug("device_discovery.found", ip=ip, port=port)
            return {
                "ip_address": ip,
                "port": port,
                "adb_address": f"{ip}:{port}",
                "discovered_at": datetime.utcnow().isoformat(),
            }
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return None
        except Exception as exc:
            logger.debug("device_discovery.probe_error", ip=ip, error=str(exc))
            return None

    async def connect_adb_device(self, ip: str, port: int = ADB_DEFAULT_PORT) -> bool:
        """
        Подключение к устройству через adb connect.
        Запускает adb connect как subprocess.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "adb", "connect", f"{ip}:{port}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=10.0
            )
            output = stdout.decode().strip()

            # Успешное подключение: "connected to" или "already connected"
            connected = "connected" in output.lower()
            logger.info(
                "adb.connect",
                ip=ip,
                port=port,
                success=connected,
                output=output,
            )
            return connected
        except FileNotFoundError:
            logger.error("adb.not_found", detail="adb binary not found in PATH")
            return False
        except asyncio.TimeoutError:
            logger.error("adb.connect_timeout", ip=ip, port=port)
            return False
        except Exception as exc:
            logger.error("adb.connect_error", ip=ip, error=str(exc))
            return False

    async def get_adb_device_info(self, serial: str) -> Dict[str, Any]:
        """
        Получение информации об устройстве через adb shell.
        Собираем модель, производителя, версию ОС, батарею, температуру.
        """
        info: Dict[str, Any] = {}

        # Набор команд для получения информации с устройства
        props = {
            "model": "ro.product.model",
            "manufacturer": "ro.product.manufacturer",
            "os_version": "ro.build.version.release",
            "screen_resolution": "persist.sys.display_size",
        }

        for field, prop in props.items():
            value = await self._adb_getprop(serial, prop)
            if value:
                info[field] = value

        # Разрешение экрана через wm size (если через getprop не получили)
        if "screen_resolution" not in info:
            wm_output = await self._adb_shell(serial, "wm size")
            if wm_output and "Physical size:" in wm_output:
                info["screen_resolution"] = wm_output.split("Physical size:")[-1].strip()

        # Уровень батареи
        battery_output = await self._adb_shell(serial, "dumpsys battery")
        if battery_output:
            for line in battery_output.splitlines():
                line = line.strip()
                if line.startswith("level:"):
                    try:
                        info["battery_level"] = int(line.split(":")[-1].strip())
                    except ValueError:
                        pass
                elif line.startswith("temperature:"):
                    try:
                        # Температура в десятых долях градуса
                        info["temperature"] = int(line.split(":")[-1].strip()) / 10.0
                    except ValueError:
                        pass

        # RAM через /proc/meminfo
        meminfo = await self._adb_shell(serial, "cat /proc/meminfo")
        if meminfo:
            for line in meminfo.splitlines():
                if line.startswith("MemTotal:"):
                    try:
                        kb = int(line.split()[1])
                        info["ram_mb"] = kb // 1024
                    except (ValueError, IndexError):
                        pass
                    break

        logger.info("device.info_collected", serial=serial, fields=list(info.keys()))
        return info

    async def _adb_getprop(self, serial: str, prop: str) -> Optional[str]:
        """Execute adb getprop for a specific property."""
        return await self._adb_shell(serial, f"getprop {prop}")

    async def _adb_shell(self, serial: str, command: str) -> Optional[str]:
        """Execute an adb shell command and return stdout."""
        try:
            process = await asyncio.create_subprocess_exec(
                "adb", "-s", serial, "shell", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(
                process.communicate(), timeout=10.0
            )
            output = stdout.decode().strip()
            return output if output else None
        except (FileNotFoundError, asyncio.TimeoutError, Exception) as exc:
            logger.debug(
                "adb.shell_error",
                serial=serial,
                command=command,
                error=str(exc),
            )
            return None

    # ═══════════════════════════════════════════════════════════
    # Отслеживание статусов устройств
    # ═══════════════════════════════════════════════════════════

    async def update_device_status(
        self,
        device_id: UUID,
        status: str,
        db: Optional[AsyncSession] = None,
    ) -> None:
        """
        Обновление статуса устройства в БД и Redis-кеше.
        Публикуем событие смены статуса для WebSocket-подписчиков.
        """
        cache_key = DEVICE_STATUS_KEY.format(device_id=device_id)
        await redis_client.set_cache(cache_key, status, ttl=300)

        # Сохраняем в БД
        close_session = False
        if db is None:
            db = async_session_factory()
            close_session = True

        try:
            await db.execute(
                update(Device)
                .where(Device.id == device_id)
                .values(
                    status=status,
                    last_seen_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
            if close_session:
                await db.commit()
        except Exception as exc:
            logger.error("device.status_update_error", device_id=str(device_id), error=str(exc))
            if close_session:
                await db.rollback()
            raise
        finally:
            if close_session:
                await db.close()

        # Оповещаем подписчиков через pub/sub
        await redis_client.publish("chimera:device_status", {
            "device_id": str(device_id),
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        })

        logger.info("device.status_updated", device_id=str(device_id), status=status)

    async def get_device_status(self, device_id: UUID) -> Optional[str]:
        """
        Получение текущего статуса устройства. Сначала проверяем Redis-кеш,
        при промахе — запрос в БД.
        """
        cache_key = DEVICE_STATUS_KEY.format(device_id=device_id)
        cached = await redis_client.get_cache(cache_key)
        if cached:
            return cached

        # Кеш промах — идём в БД
        async with async_session_factory() as db:
            result = await db.execute(
                select(Device.status).where(Device.id == device_id)
            )
            status = result.scalar_one_or_none()
            if status:
                await redis_client.set_cache(cache_key, status, ttl=300)
            return status

    async def process_heartbeat(self, device_id: UUID, heartbeat_data: Dict[str, Any]) -> None:
        """
        Обработка heartbeat от устройства. Обновляем last_seen_at и статус.
        Если устройство было офлайн — переводим в online.
        """
        heartbeat_key = DEVICE_HEARTBEAT_KEY.format(device_id=device_id)
        await redis_client.set_cache(heartbeat_key, datetime.utcnow().isoformat(), ttl=HEARTBEAT_TIMEOUT_SECONDS)

        current_status = await self.get_device_status(device_id)
        if current_status != "online":
            # Устройство вернулось в сеть
            await self.update_device_status(device_id, "online")

        # Обновляем дополнительную информацию из heartbeat (батарея, температура и т.д.)
        if heartbeat_data:
            await self.update_device_info(device_id, heartbeat_data)

    async def check_stale_devices(self) -> List[UUID]:
        """
        Проверка устройств, которые не отправляли heartbeat дольше таймаута.
        Переводим их в статус offline.
        """
        stale_devices: List[UUID] = []

        async with async_session_factory() as db:
            result = await db.execute(
                select(Device).where(Device.status == "online")
            )
            online_devices = result.scalars().all()

            for device in online_devices:
                heartbeat_key = DEVICE_HEARTBEAT_KEY.format(device_id=device.id)
                last_heartbeat = await redis_client.get_cache(heartbeat_key)

                if last_heartbeat is None:
                    # Нет heartbeat в кеше — устройство считается неактивным
                    await self.update_device_status(device.id, "offline", db)
                    stale_devices.append(device.id)

            if stale_devices:
                await db.commit()

        if stale_devices:
            logger.info("device.stale_check", offline_count=len(stale_devices))

        return stale_devices

    # ═══════════════════════════════════════════════════════════
    # Отправка команд устройствам через Redis pub/sub
    # ═══════════════════════════════════════════════════════════

    async def send_command(
        self,
        device_id: UUID,
        command: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Отправка команды на устройство через Redis pub/sub.
        Устройство подписано на канал device:{device_id}:commands.
        """
        channel = DEVICE_COMMAND_CHANNEL.format(device_id=device_id)
        message = {
            "command": command,
            "params": params or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        await redis_client.publish(channel, message)
        logger.info(
            "device.command_sent",
            device_id=str(device_id),
            command=command,
        )

    async def send_command_to_all(
        self,
        user_id: UUID,
        command: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Отправка команды на все онлайн-устройства пользователя.
        Возвращает количество устройств, которым была отправлена команда.
        """
        async with async_session_factory() as db:
            result = await db.execute(
                select(Device).where(
                    Device.user_id == user_id,
                    Device.status == "online",
                )
            )
            devices = result.scalars().all()

        sent = 0
        for device in devices:
            await self.send_command(device.id, command, params)
            sent += 1

        logger.info(
            "device.broadcast_command",
            user_id=str(user_id),
            command=command,
            device_count=sent,
        )
        return sent

    async def send_task_to_device(
        self,
        device_id: UUID,
        task_id: UUID,
        task_type: str,
        payload: Dict[str, Any],
    ) -> None:
        """
        Отправка задачи на устройство для выполнения.
        Специальная команда execute_task.
        """
        await self.send_command(device_id, "execute_task", {
            "task_id": str(task_id),
            "task_type": task_type,
            "payload": payload,
        })

    # ═══════════════════════════════════════════════════════════
    # Обновление информации об устройстве
    # ═══════════════════════════════════════════════════════════

    async def update_device_info(
        self,
        device_id: UUID,
        info: Dict[str, Any],
        db: Optional[AsyncSession] = None,
    ) -> None:
        """
        Обновление информации об устройстве: батарея, температура, IP и т.д.
        Принимает словарь с полями, которые нужно обновить.
        """
        # Фильтруем только допустимые поля модели Device
        allowed_fields = {
            "battery_level", "temperature", "ip_address", "external_ip",
            "vpn_active", "proxy_info", "model", "manufacturer",
            "os_version", "screen_resolution", "ram_mb",
        }
        update_values = {k: v for k, v in info.items() if k in allowed_fields and v is not None}

        if not update_values:
            return

        update_values["last_seen_at"] = datetime.utcnow()
        update_values["updated_at"] = datetime.utcnow()

        close_session = False
        if db is None:
            db = async_session_factory()
            close_session = True

        try:
            await db.execute(
                update(Device)
                .where(Device.id == device_id)
                .values(**update_values)
            )
            if close_session:
                await db.commit()
        except Exception as exc:
            logger.error("device.info_update_error", device_id=str(device_id), error=str(exc))
            if close_session:
                await db.rollback()
            raise
        finally:
            if close_session:
                await db.close()

        # Кешируем обновленную информацию
        info_key = DEVICE_INFO_KEY.format(device_id=device_id)
        await redis_client.set_cache(info_key, update_values, ttl=300)

        logger.debug(
            "device.info_updated",
            device_id=str(device_id),
            fields=list(update_values.keys()),
        )

    async def get_all_devices_status(self, user_id: UUID) -> List[Dict[str, Any]]:
        """
        Получение статуса всех устройств пользователя.
        Используется для дашборда.
        """
        async with async_session_factory() as db:
            result = await db.execute(
                select(Device).where(Device.user_id == user_id)
            )
            devices = result.scalars().all()

        statuses = []
        for device in devices:
            statuses.append({
                "id": str(device.id),
                "name": device.name,
                "device_type": device.device_type,
                "status": device.status,
                "battery_level": device.battery_level,
                "temperature": device.temperature,
                "ip_address": str(device.ip_address) if device.ip_address else None,
                "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
            })

        return statuses

    # ═══════════════════════════════════════════════════════════
    # Фоновый мониторинг (запуск/остановка)
    # ═══════════════════════════════════════════════════════════

    async def start_monitoring(self, interval_seconds: int = 60) -> None:
        """
        Запуск фонового мониторинга устройств.
        Периодически проверяет stale-устройства.
        """
        if self._running:
            logger.warning("device.monitoring_already_running")
            return

        self._running = True
        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(interval_seconds)
        )
        logger.info("device.monitoring_started", interval=interval_seconds)

    async def stop_monitoring(self) -> None:
        """Остановка фонового мониторинга."""
        self._running = False
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("device.monitoring_stopped")

    async def _monitoring_loop(self, interval: int) -> None:
        """Цикл фонового мониторинга: проверка heartbeat, обновление статусов."""
        while self._running:
            try:
                await self.check_stale_devices()
            except Exception as exc:
                logger.error("device.monitoring_error", error=str(exc))
            await asyncio.sleep(interval)


# Singleton instance
device_manager = DeviceManager()
