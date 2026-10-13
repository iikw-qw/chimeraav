"""
Сервис планировщика: APScheduler интеграция, выполнение scheduler_plans,
СИПР-микширование фотографий, постановка задач на публикацию.
Зависит от: config, database, redis_client, models, task_dispatcher
"""

import asyncio
import random
from datetime import datetime, date, timedelta, time
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.scheduler_plan import SchedulerPlan
from app.models.dataset import Dataset
from app.models.post import Post
from app.models.task import Task
from app.models.account import SocialAccount
from app.services.redis_client import redis_client
from app.services.comment_analyzer import comment_analyzer

logger = structlog.get_logger()

# Redis key для отслеживания использования фотографий в СИПР-микшировании
PHOTO_USAGE_KEY = "chimera:sipr:photo_usage:{dataset_id}"

# Временные слоты для публикации (часы в формате UTC)
DEFAULT_POST_HOURS = [9, 12, 15, 18, 21]


class SchedulerService:
    """
    Управление планировщиком APScheduler.
    Выполняет scheduler_plans: создаёт задачи на публикацию для каждого запланированного поста.
    Реализует СИПР-микширование фотографий для равномерного использования датасета.
    """

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._plan_check_job_id = "chimera_plan_checker"

    # ═══════════════════════════════════════════════════════════
    # Запуск и остановка планировщика (lifespan)
    # ═══════════════════════════════════════════════════════════

    async def start(self) -> None:
        """
        Запуск APScheduler. Вызывается при старте приложения в lifespan.
        Регистрирует периодическую задачу проверки планов.
        """
        self.scheduler = AsyncIOScheduler(
            timezone="UTC",
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 300,
            },
        )

        # Проверка планов каждые 5 минут
        self.scheduler.add_job(
            self._check_and_execute_plans,
            trigger=IntervalTrigger(minutes=5),
            id=self._plan_check_job_id,
            replace_existing=True,
            name="Проверка и выполнение планов расписания",
        )

        # Автоответ: обработка pending-комментариев каждые 10 минут
        self.scheduler.add_job(
            self._process_auto_replies,
            trigger=IntervalTrigger(minutes=10),
            id="chimera_auto_reply_process",
            replace_existing=True,
            name="Обработка новых комментариев для автоответа",
        )

        # Автоответ: отправка запланированных ответов каждые 5 минут
        self.scheduler.add_job(
            self._send_scheduled_replies,
            trigger=IntervalTrigger(minutes=5),
            id="chimera_auto_reply_send",
            replace_existing=True,
            name="Отправка запланированных автоответов",
        )

        self.scheduler.start()
        logger.info("scheduler.started")

        # Сразу выполняем первую проверку
        asyncio.create_task(self._check_and_execute_plans())

    async def stop(self) -> None:
        """Остановка APScheduler при завершении приложения."""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("scheduler.stopped")

    # ═══════════════════════════════════════════════════════════
    # Проверка и выполнение планов
    # ═══════════════════════════════════════════════════════════

    async def _check_and_execute_plans(self) -> None:
        """
        Проверяем все активные планы и создаём задачи для тех,
        которые должны выполниться сейчас.
        """
        try:
            async with async_session_factory() as db:
                today = date.today()
                now = datetime.utcnow()

                # Получаем все активные планы
                result = await db.execute(
                    select(SchedulerPlan).where(
                        SchedulerPlan.status == "active",
                    )
                )
                plans = result.scalars().all()

                for plan in plans:
                    try:
                        await self._evaluate_plan(db, plan, today, now)
                    except Exception as exc:
                        logger.error(
                            "scheduler.plan_error",
                            plan_id=str(plan.id),
                            plan_name=plan.name,
                            error=str(exc),
                        )

                await db.commit()

        except Exception as exc:
            logger.error("scheduler.check_error", error=str(exc))

    async def _evaluate_plan(
        self,
        db: AsyncSession,
        plan: SchedulerPlan,
        today: date,
        now: datetime,
    ) -> None:
        """
        Оценка одного плана: нужно ли создавать задачи на сегодня.
        Проверяем дату начала/окончания, частоту, последний запуск.
        """
        # Проверка дат действия плана
        if plan.start_date and today < plan.start_date:
            return
        if plan.end_date and today > plan.end_date:
            # План истёк — переводим в завершённый статус
            plan.status = "completed"
            logger.info("scheduler.plan_completed", plan_id=str(plan.id), plan_name=plan.name)
            return

        # Проверка: нужно ли запускать план сегодня по частоте
        if not self._should_run_today(plan, today):
            return

        # Проверка: не запускали ли план уже сегодня
        if plan.last_run_at:
            last_run_date = plan.last_run_at.date() if isinstance(plan.last_run_at, datetime) else plan.last_run_at
            if last_run_date == today:
                return

        logger.info(
            "scheduler.executing_plan",
            plan_id=str(plan.id),
            plan_name=plan.name,
            posts_per_day=plan.posts_per_day,
        )

        # Создаём задачи на публикацию для каждого аккаунта
        await self._create_posting_tasks(db, plan, today)

        # Обновляем время последнего запуска
        plan.last_run_at = now

    def _should_run_today(self, plan: SchedulerPlan, today: date) -> bool:
        """
        Проверка, нужно ли запускать план сегодня в зависимости от частоты.
        Поддерживаемые значения: daily, weekdays, every_2_days, every_3_days, weekly.
        """
        frequency = (plan.frequency or "daily").lower()

        if frequency == "daily":
            return True
        elif frequency == "weekdays":
            # Только будние дни (пн-пт)
            return today.weekday() < 5
        elif frequency == "every_2_days":
            if plan.start_date:
                delta = (today - plan.start_date).days
                return delta % 2 == 0
            return today.day % 2 == 0
        elif frequency == "every_3_days":
            if plan.start_date:
                delta = (today - plan.start_date).days
                return delta % 3 == 0
            return today.day % 3 == 0
        elif frequency == "weekly":
            if plan.start_date:
                return today.weekday() == plan.start_date.weekday()
            return today.weekday() == 0  # Понедельник по умолчанию
        else:
            # Неизвестная частота — запускаем каждый день
            return True

    # ═══════════════════════════════════════════════════════════
    # Создание задач на публикацию
    # ═══════════════════════════════════════════════════════════

    async def _create_posting_tasks(
        self,
        db: AsyncSession,
        plan: SchedulerPlan,
        today: date,
    ) -> None:
        """
        Создание задач на публикацию для каждого аккаунта в плане.
        Подбирает фотографии через СИПР-микширование, рассчитывает время публикации.
        """
        account_ids = plan.accounts or []
        if not account_ids:
            logger.warning(
                "scheduler.no_accounts",
                plan_id=str(plan.id),
            )
            return

        # Загружаем датасет для подбора фотографий
        dataset = None
        if plan.dataset_id:
            result = await db.execute(
                select(Dataset).where(Dataset.id == plan.dataset_id)
            )
            dataset = result.scalar_one_or_none()

        # Генерируем временные слоты для публикаций
        time_slots = self._generate_time_slots(plan.posts_per_day, today)

        for account_id_raw in account_ids:
            try:
                account_id = UUID(str(account_id_raw))
            except (ValueError, TypeError):
                logger.warning(
                    "scheduler.invalid_account_id",
                    plan_id=str(plan.id),
                    account_id=str(account_id_raw),
                )
                continue

            # Проверяем, что аккаунт существует и активен
            result = await db.execute(
                select(SocialAccount).where(
                    SocialAccount.id == account_id,
                    SocialAccount.status == "active",
                )
            )
            account = result.scalar_one_or_none()
            if not account:
                logger.warning(
                    "scheduler.account_not_found_or_inactive",
                    account_id=str(account_id),
                )
                continue

            for i, scheduled_at in enumerate(time_slots):
                # Подбор фотографий для поста через СИПР
                photos = []
                if dataset:
                    photos = await self.select_photos_sipr(
                        dataset_id=dataset.id,
                        dataset_photos=dataset.photos or [],
                        count=random.randint(1, 3),
                    )

                # Создаём пост в БД
                post = Post(
                    id=uuid4(),
                    user_id=plan.user_id,
                    account_id=account_id,
                    dataset_id=plan.dataset_id,
                    photos=photos,
                    caption=None,  # Капшен генерируется на устройстве (LLM/шаблон)
                    platform=account.platform,
                    status="scheduled",
                    scheduled_at=scheduled_at,
                )
                db.add(post)
                await db.flush()

                # Создаём задачу на выполнение
                task = Task(
                    id=uuid4(),
                    user_id=plan.user_id,
                    device_id=account.device_id,
                    account_id=account_id,
                    task_type="post",
                    status="pending",
                    priority=5,
                    payload={
                        "post_id": str(post.id),
                        "photos": photos,
                        "caption_style": plan.caption_style or "auto",
                        "platform": account.platform,
                        "scheduled_at": scheduled_at.isoformat(),
                    },
                    scheduled_at=scheduled_at,
                    max_retries=3,
                )
                db.add(task)
                await db.flush()

                # Ставим задачу в очередь Redis через task_dispatcher
                from app.services.task_dispatcher import task_dispatcher
                await task_dispatcher.enqueue_task(
                    task_id=task.id,
                    task_type="post",
                    device_id=account.device_id,
                    account_id=account_id,
                    payload=task.payload,
                )

                logger.info(
                    "scheduler.task_created",
                    plan_id=str(plan.id),
                    task_id=str(task.id),
                    post_id=str(post.id),
                    account=account.username,
                    scheduled_at=scheduled_at.isoformat(),
                )

    def _generate_time_slots(
        self,
        posts_per_day: int,
        target_date: date,
    ) -> List[datetime]:
        """
        Генерация временных слотов для публикаций.
        Равномерно распределяет посты в течение дня с рандомным смещением.
        """
        slots: List[datetime] = []

        if posts_per_day <= 0:
            return slots

        if posts_per_day <= len(DEFAULT_POST_HOURS):
            # Выбираем из предопределённых часов
            selected_hours = sorted(random.sample(DEFAULT_POST_HOURS, posts_per_day))
        else:
            # Распределяем равномерно по активным часам (8:00 - 23:00)
            active_start = 8
            active_end = 23
            step = (active_end - active_start) / posts_per_day
            selected_hours = [
                int(active_start + step * i) for i in range(posts_per_day)
            ]

        for hour in selected_hours:
            # Рандомное смещение по минутам для естественности
            minute = random.randint(0, 55)
            slot = datetime.combine(target_date, time(hour=hour, minute=minute))
            slots.append(slot)

        return slots

    # ═══════════════════════════════════════════════════════════
    # СИПР-микширование фотографий (равномерное использование датасета)
    # ═══════════════════════════════════════════════════════════

    async def select_photos_sipr(
        self,
        dataset_id: UUID,
        dataset_photos: List[str],
        count: int = 1,
    ) -> List[str]:
        """
        СИПР (Система Индексного Подбора Ресурсов) — выбор фотографий
        с равномерным использованием всего датасета.

        Каждая фотография имеет счётчик использования в Redis.
        Алгоритм выбирает наименее использованные фотографии,
        обеспечивая равномерную ротацию контента.
        """
        if not dataset_photos:
            return []

        count = min(count, len(dataset_photos))
        usage_key = PHOTO_USAGE_KEY.format(dataset_id=dataset_id)

        # Получаем текущие счётчики использования для всех фотографий
        usage_counts: Dict[str, int] = {}
        for photo in dataset_photos:
            cached = await redis_client.hget(usage_key, photo)
            usage_counts[photo] = int(cached) if cached is not None else 0

        # Сортируем по количеству использований (наименьшее первое)
        sorted_photos = sorted(usage_counts.items(), key=lambda x: x[1])

        # Среди фотографий с минимальным использованием — рандомный выбор
        min_usage = sorted_photos[0][1] if sorted_photos else 0

        # Кандидаты: все фотографии с минимальным использованием
        candidates = [
            photo for photo, usage in sorted_photos
            if usage <= min_usage + 1  # Допускаем разницу в 1 для разнообразия
        ]

        # Если кандидатов меньше, чем нужно — берём больше из общего списка
        if len(candidates) < count:
            remaining = [p for p, _ in sorted_photos if p not in candidates]
            candidates.extend(remaining[:count - len(candidates)])

        # Выбираем случайным образом из кандидатов
        selected = random.sample(candidates, min(count, len(candidates)))

        # Обновляем счётчики использования
        for photo in selected:
            new_count = usage_counts.get(photo, 0) + 1
            await redis_client.hset(usage_key, photo, str(new_count))

        # Обновляем usage_stats в датасете (через Redis-кеш, БД обновится при сохранении)
        total_uses = sum(usage_counts.get(p, 0) for p in dataset_photos) + len(selected)
        await redis_client.set_cache(
            f"chimera:dataset:stats:{dataset_id}",
            {
                "total_uses": total_uses,
                "unique_used": len([p for p in dataset_photos if usage_counts.get(p, 0) > 0 or p in selected]),
                "total_photos": len(dataset_photos),
            },
            ttl=3600,
        )

        logger.debug(
            "sipr.photos_selected",
            dataset_id=str(dataset_id),
            selected_count=len(selected),
            min_usage=min_usage,
        )

        return selected

    async def reset_photo_usage(self, dataset_id: UUID) -> None:
        """
        Сброс счётчиков использования для датасета.
        Вызывается при полном обороте или ручном сбросе.
        """
        usage_key = PHOTO_USAGE_KEY.format(dataset_id=dataset_id)
        await redis_client.delete_cache(usage_key)
        logger.info("sipr.usage_reset", dataset_id=str(dataset_id))

    async def get_photo_usage_stats(self, dataset_id: UUID) -> Dict[str, Any]:
        """Статистика использования фотографий в датасете."""
        usage_key = PHOTO_USAGE_KEY.format(dataset_id=dataset_id)
        usage_data = await redis_client.hgetall(usage_key)

        counts = [int(v) for v in usage_data.values()] if usage_data else []
        return {
            "total_photos_tracked": len(counts),
            "total_uses": sum(counts),
            "min_uses": min(counts) if counts else 0,
            "max_uses": max(counts) if counts else 0,
            "avg_uses": round(sum(counts) / len(counts), 2) if counts else 0.0,
            "evenness_score": round(
                1.0 - (max(counts) - min(counts)) / max(max(counts), 1), 2
            ) if counts else 1.0,
        }

    # ═══════════════════════════════════════════════════════════
    # Автоответ на комментарии
    # ═══════════════════════════════════════════════════════════

    async def _process_auto_replies(self) -> None:
        try:
            count = await comment_analyzer.process_pending_comments()
            if count > 0:
                logger.info("scheduler.auto_reply_processed", count=count)
        except Exception as exc:
            logger.error("scheduler.auto_reply_process_error", error=str(exc))

    async def _send_scheduled_replies(self) -> None:
        try:
            count = await comment_analyzer.send_scheduled_responses()
            if count > 0:
                logger.info("scheduler.auto_reply_sent", count=count)
        except Exception as exc:
            logger.error("scheduler.auto_reply_send_error", error=str(exc))

    # ═══════════════════════════════════════════════════════════
    # Ручное управление планами из API
    # ═══════════════════════════════════════════════════════════

    async def trigger_plan_now(self, plan_id: UUID) -> int:
        """
        Принудительный запуск плана прямо сейчас.
        Возвращает количество созданных задач.
        """
        async with async_session_factory() as db:
            result = await db.execute(
                select(SchedulerPlan).where(SchedulerPlan.id == plan_id)
            )
            plan = result.scalar_one_or_none()

            if not plan:
                logger.warning("scheduler.plan_not_found", plan_id=str(plan_id))
                return 0

            if plan.status != "active":
                logger.warning(
                    "scheduler.plan_not_active",
                    plan_id=str(plan_id),
                    status=plan.status,
                )
                return 0

            today = date.today()
            tasks_before = await db.execute(
                select(Task).where(
                    Task.user_id == plan.user_id,
                    Task.task_type == "post",
                    Task.status == "pending",
                )
            )
            count_before = len(tasks_before.scalars().all())

            await self._create_posting_tasks(db, plan, today)
            plan.last_run_at = datetime.utcnow()
            await db.commit()

            tasks_after = await db.execute(
                select(Task).where(
                    Task.user_id == plan.user_id,
                    Task.task_type == "post",
                    Task.status == "pending",
                )
            )
            count_after = len(tasks_after.scalars().all())
            created = count_after - count_before

        logger.info(
            "scheduler.plan_triggered",
            plan_id=str(plan_id),
            tasks_created=created,
        )
        return created

    async def add_custom_job(
        self,
        job_id: str,
        cron_expression: str,
        callback,
        **kwargs,
    ) -> None:
        """
        Добавление пользовательской cron-задачи в планировщик.
        cron_expression в формате: "minute hour day_of_month month day_of_week"
        """
        if not self.scheduler:
            logger.error("scheduler.not_started")
            return

        parts = cron_expression.split()
        if len(parts) != 5:
            logger.error(
                "scheduler.invalid_cron",
                cron=cron_expression,
                detail="Expected 5 fields: minute hour day month day_of_week",
            )
            return

        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )

        self.scheduler.add_job(
            callback,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            **kwargs,
        )
        logger.info("scheduler.custom_job_added", job_id=job_id, cron=cron_expression)

    async def remove_job(self, job_id: str) -> bool:
        """Удаление задачи из планировщика."""
        if not self.scheduler:
            return False
        try:
            self.scheduler.remove_job(job_id)
            logger.info("scheduler.job_removed", job_id=job_id)
            return True
        except Exception:
            logger.warning("scheduler.job_not_found", job_id=job_id)
            return False

    def get_scheduled_jobs(self) -> List[Dict[str, Any]]:
        """Список всех запланированных задач."""
        if not self.scheduler:
            return []

        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name or job.id,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return jobs


# Singleton instance
scheduler_service = SchedulerService()
