"""
Диспетчер задач: чтение из Redis Stream, распределение по устройствам,
повторные попытки, Dead Letter Queue.
Зависит от: config, database, redis_client, models/task, models/device, device_manager
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
from app.models.task import Task
from app.models.device import Device
from app.services.redis_client import redis_client

logger = structlog.get_logger()

# Redis Stream / consumer group names
TASK_STREAM = "chimera:tasks"
TASK_GROUP = "task_workers"
CONSUMER_NAME = "dispatcher-main"

# Dead Letter Queue
DLQ_STREAM = "chimera:tasks:dlq"

# Максимальное количество повторных попыток
MAX_RETRIES = 3

# Базовая задержка для экспоненциального backoff (секунды)
BASE_BACKOFF_SECONDS = 5.0

# Множитель backoff
BACKOFF_MULTIPLIER = 2.0


class TaskDispatcher:
    """
    Диспетчер задач. Читает задачи из Redis Stream consumer group,
    распределяет по устройствам, обрабатывает повторные попытки
    и Dead Letter Queue для окончательно провалившихся задач.
    """

    def __init__(self):
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    # ═══════════════════════════════════════════════════════════
    # Запуск и остановка worker-цикла
    # ═══════════════════════════════════════════════════════════

    async def start(self) -> None:
        """Запуск worker-цикла чтения задач из Redis Stream."""
        if self._running:
            logger.warning("task_dispatcher.already_running")
            return

        # Создаём consumer group если она ещё не существует
        await redis_client.create_consumer_group(TASK_STREAM, TASK_GROUP)
        await redis_client.create_consumer_group(DLQ_STREAM, "dlq_workers")

        self._running = True
        self._worker_task = asyncio.create_task(self._consume_loop())
        logger.info("task_dispatcher.started", stream=TASK_STREAM, group=TASK_GROUP)

    async def stop(self) -> None:
        """Остановка worker-цикла."""
        self._running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("task_dispatcher.stopped")

    async def _consume_loop(self) -> None:
        """
        Основной цикл чтения задач из Redis Stream.
        Блокирующее чтение с таймаутом 5 секунд.
        """
        while self._running:
            try:
                messages = await redis_client.read_tasks(
                    stream=TASK_STREAM,
                    group=TASK_GROUP,
                    consumer=CONSUMER_NAME,
                    count=10,
                    block=5000,
                )

                for msg in messages:
                    msg_id = msg["id"]
                    data = msg["data"]

                    try:
                        await self._dispatch_task(msg_id, data)
                        # Подтверждаем успешную обработку
                        await redis_client.ack_task(TASK_STREAM, TASK_GROUP, msg_id)
                    except Exception as exc:
                        logger.error(
                            "task_dispatcher.dispatch_error",
                            msg_id=msg_id,
                            error=str(exc),
                        )
                        # Всё равно подтверждаем — retry обрабатывается на уровне задачи
                        await redis_client.ack_task(TASK_STREAM, TASK_GROUP, msg_id)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("task_dispatcher.consume_error", error=str(exc))
                await asyncio.sleep(2.0)

    # ═══════════════════════════════════════════════════════════
    # Диспетчеризация задач на устройства
    # ═══════════════════════════════════════════════════════════

    async def _dispatch_task(self, msg_id: str, data: Dict[str, Any]) -> None:
        """
        Распределение задачи на устройство. Определяем целевое устройство,
        проверяем его доступность, отправляем команду.
        """
        task_id_str = data.get("task_id")
        if not task_id_str:
            logger.warning("task_dispatcher.missing_task_id", msg_id=msg_id)
            return

        task_id = UUID(task_id_str)
        task_type = data.get("task_type", "unknown")
        device_id_str = data.get("device_id")
        account_id_str = data.get("account_id")
        payload = data.get("payload", {})

        logger.info(
            "task_dispatcher.dispatching",
            task_id=task_id_str,
            task_type=task_type,
            device_id=device_id_str,
        )

        async with async_session_factory() as db:
            # Загружаем задачу из БД
            result = await db.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()

            if not task:
                logger.warning("task_dispatcher.task_not_found", task_id=task_id_str)
                return

            # Задачи в финальных статусах не обрабатываем
            if task.status in ("completed", "dead", "cancelled"):
                logger.info(
                    "task_dispatcher.skip_final_status",
                    task_id=task_id_str,
                    status=task.status,
                )
                return

            # Определяем устройство для выполнения задачи
            device = await self._resolve_device(db, task, device_id_str)

            if not device:
                # Нет доступного устройства — ставим задачу на retry
                await self._handle_no_device(db, task)
                await db.commit()
                return

            # Привязываем устройство к задаче если не было
            if not task.device_id:
                task.device_id = device.id

            # Переводим задачу в статус running
            task.status = "running"
            task.started_at = datetime.utcnow()
            await db.commit()

        # Отправляем команду на устройство через Redis pub/sub
        from app.services.device_manager import device_manager
        await device_manager.send_task_to_device(
            device_id=device.id,
            task_id=task_id,
            task_type=task_type,
            payload=payload,
        )

        logger.info(
            "task_dispatcher.dispatched",
            task_id=task_id_str,
            device_id=str(device.id),
            device_name=device.name,
        )

    async def _resolve_device(
        self,
        db: AsyncSession,
        task: Task,
        device_id_str: Optional[str],
    ) -> Optional[Device]:
        """
        Определяем целевое устройство для задачи.
        Если device_id указан — проверяем его доступность.
        Если нет — выбираем наименее загруженное online-устройство пользователя.
        """
        if device_id_str:
            device_id = UUID(device_id_str)
            result = await db.execute(
                select(Device).where(
                    Device.id == device_id,
                    Device.status == "online",
                )
            )
            device = result.scalar_one_or_none()
            if device:
                return device
            logger.warning(
                "task_dispatcher.target_device_unavailable",
                device_id=device_id_str,
            )

        # Автоматический выбор устройства: online, принадлежит пользователю
        result = await db.execute(
            select(Device)
            .where(
                Device.user_id == task.user_id,
                Device.status == "online",
            )
            .order_by(Device.last_seen_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _handle_no_device(self, db: AsyncSession, task: Task) -> None:
        """
        Обработка случая, когда нет доступного устройства.
        Задачу возвращаем в pending с задержкой.
        """
        task.status = "pending"
        task.error_message = "Нет доступного устройства для выполнения задачи"
        logger.warning(
            "task_dispatcher.no_device_available",
            task_id=str(task.id),
            user_id=str(task.user_id),
        )

    # ═══════════════════════════════════════════════════════════
    # Постановка задачи в очередь (из API или планировщика)
    # ═══════════════════════════════════════════════════════════

    async def enqueue_task(
        self,
        task_id: UUID,
        task_type: str,
        device_id: Optional[UUID] = None,
        account_id: Optional[UUID] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Постановка задачи в Redis Stream.
        Возвращает message_id из Redis Stream.
        """
        stream_data = {
            "task_id": str(task_id),
            "task_type": task_type,
            "device_id": str(device_id) if device_id else None,
            "account_id": str(account_id) if account_id else None,
            "payload": payload or {},
        }

        msg_id = await redis_client.add_task(TASK_STREAM, stream_data)

        logger.info(
            "task_dispatcher.enqueued",
            task_id=str(task_id),
            task_type=task_type,
            stream_msg_id=msg_id,
        )
        return msg_id

    # ═══════════════════════════════════════════════════════════
    # Обработка результата выполнения задачи
    # ═══════════════════════════════════════════════════════════

    async def handle_task_result(
        self,
        task_id: UUID,
        success: bool,
        result_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Обработка результата выполнения задачи от устройства.
        При ошибке — retry с экспоненциальным backoff или перенос в DLQ.
        """
        async with async_session_factory() as db:
            result = await db.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()

            if not task:
                logger.warning("task_dispatcher.result_task_not_found", task_id=str(task_id))
                return

            if success:
                # Задача выполнена успешно
                task.status = "completed"
                task.completed_at = datetime.utcnow()
                task.result = result_data or {}
                task.error_message = None
                await db.commit()

                logger.info("task_dispatcher.task_completed", task_id=str(task_id))

                # Публикуем событие завершения для WebSocket и уведомлений
                await redis_client.publish("chimera:task_results", {
                    "task_id": str(task_id),
                    "status": "completed",
                    "task_type": task.task_type,
                    "result": result_data or {},
                    "timestamp": datetime.utcnow().isoformat(),
                })
            else:
                # Задача провалилась — проверяем лимит retry
                await self._handle_task_failure(db, task, error_message)
                await db.commit()

    async def _handle_task_failure(
        self,
        db: AsyncSession,
        task: Task,
        error_message: Optional[str],
    ) -> None:
        """
        Обработка провала задачи. Если retry не исчерпаны — повторная
        постановка с экспоненциальным backoff. Иначе — Dead Letter Queue.
        """
        task.retry_count += 1
        task.error_message = error_message

        max_retries = task.max_retries if task.max_retries is not None else MAX_RETRIES

        if task.retry_count < max_retries:
            # Ещё есть попытки — планируем retry с backoff
            backoff_delay = BASE_BACKOFF_SECONDS * (BACKOFF_MULTIPLIER ** (task.retry_count - 1))
            task.status = "retrying"

            logger.info(
                "task_dispatcher.retrying",
                task_id=str(task.id),
                retry_count=task.retry_count,
                max_retries=max_retries,
                backoff_seconds=backoff_delay,
                error=error_message,
            )

            # Планируем повторную постановку в очередь с задержкой
            asyncio.create_task(
                self._delayed_requeue(task, backoff_delay)
            )
        else:
            # Исчерпаны все попытки — отправляем в Dead Letter Queue
            task.status = "dead"
            task.completed_at = datetime.utcnow()
            await self._move_to_dlq(task, error_message)

    async def _delayed_requeue(self, task: Task, delay_seconds: float) -> None:
        """
        Повторная постановка задачи в очередь после задержки (backoff).
        """
        await asyncio.sleep(delay_seconds)

        try:
            await self.enqueue_task(
                task_id=task.id,
                task_type=task.task_type,
                device_id=task.device_id,
                account_id=task.account_id,
                payload=task.payload,
            )
            logger.info(
                "task_dispatcher.requeued",
                task_id=str(task.id),
                retry_count=task.retry_count,
            )
        except Exception as exc:
            logger.error(
                "task_dispatcher.requeue_error",
                task_id=str(task.id),
                error=str(exc),
            )

    async def _move_to_dlq(self, task: Task, error_message: Optional[str]) -> None:
        """
        Перемещение задачи в Dead Letter Queue после исчерпания попыток.
        Задача сохраняется в отдельный Redis Stream для последующего анализа.
        """
        dlq_data = {
            "task_id": str(task.id),
            "task_type": task.task_type,
            "user_id": str(task.user_id),
            "device_id": str(task.device_id) if task.device_id else None,
            "account_id": str(task.account_id) if task.account_id else None,
            "payload": task.payload,
            "retry_count": task.retry_count,
            "error_message": error_message or "Unknown error",
            "failed_at": datetime.utcnow().isoformat(),
        }

        await redis_client.add_task(DLQ_STREAM, dlq_data)

        logger.error(
            "task_dispatcher.moved_to_dlq",
            task_id=str(task.id),
            task_type=task.task_type,
            retry_count=task.retry_count,
            error=error_message,
        )

        # Публикуем событие для уведомлений
        await redis_client.publish("chimera:task_results", {
            "task_id": str(task.id),
            "status": "dead",
            "task_type": task.task_type,
            "error": error_message,
            "timestamp": datetime.utcnow().isoformat(),
        })

    # ═══════════════════════════════════════════════════════════
    # Обновление статуса задачи
    # ═══════════════════════════════════════════════════════════

    async def update_task_status(
        self,
        task_id: UUID,
        status: str,
        result_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Прямое обновление статуса задачи в БД.
        Используется для промежуточных обновлений (progress и т.д.).
        """
        async with async_session_factory() as db:
            values: Dict[str, Any] = {"status": status}

            if status == "running":
                values["started_at"] = datetime.utcnow()
            elif status in ("completed", "failed", "dead"):
                values["completed_at"] = datetime.utcnow()

            if result_data is not None:
                values["result"] = result_data
            if error_message is not None:
                values["error_message"] = error_message

            await db.execute(
                update(Task).where(Task.id == task_id).values(**values)
            )
            await db.commit()

        logger.info(
            "task_dispatcher.status_updated",
            task_id=str(task_id),
            status=status,
        )

    # ═══════════════════════════════════════════════════════════
    # Информация о DLQ
    # ═══════════════════════════════════════════════════════════

    async def get_dlq_count(self) -> int:
        """Количество задач в Dead Letter Queue."""
        try:
            info = await redis_client.redis.xlen(DLQ_STREAM)
            return info
        except Exception:
            return 0

    async def retry_dlq_task(self, task_id: UUID) -> bool:
        """
        Повторная постановка задачи из DLQ в основную очередь.
        Сбрасывает счётчик retry.
        """
        async with async_session_factory() as db:
            result = await db.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()

            if not task or task.status != "dead":
                return False

            # Сбрасываем счётчик retry, переводим в pending
            task.status = "pending"
            task.retry_count = 0
            task.error_message = None
            task.completed_at = None
            await db.commit()

        # Ставим обратно в очередь
        await self.enqueue_task(
            task_id=task.id,
            task_type=task.task_type,
            device_id=task.device_id,
            account_id=task.account_id,
            payload=task.payload,
        )

        logger.info("task_dispatcher.dlq_retried", task_id=str(task_id))
        return True


# Singleton instance
task_dispatcher = TaskDispatcher()
