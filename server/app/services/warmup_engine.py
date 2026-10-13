"""
Движок прогрева аккаунтов: эмуляция человеческого поведения.
Действия с курсором, пуассоновские задержки, адаптивный коэффициент,
уникальные паттерны по seed = account_id.
Зависит от: config.py, database.py, redis_client.py, models/
"""

import asyncio
import hashlib
import math
import random
import subprocess
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.account import SocialAccount
from app.models.device import Device
from app.models.log import ActionLog
from app.models.task import Task
from app.services.redis_client import redis_client

logger = structlog.get_logger(__name__)

# ═══════════════════════════════════════════════════════════════
# Константы
# ═══════════════════════════════════════════════════════════════

# Poisson distribution parameters
POISSON_LAMBDA = 1.5
DELAY_MIN = 0.5   # seconds
DELAY_MAX = 4.0   # seconds

# Adaptive coefficient update interval (seconds)
COEFFICIENT_UPDATE_INTERVAL = 60

# Redis keys
WARMUP_COEFFICIENT_KEY = "chimera:warmup_coefficient"
WARMUP_STATS_PREFIX = "chimera:warmup:stats"
WARMUP_SESSION_PREFIX = "chimera:warmup:session"

# Warmup action weights (базовые, модифицируются паттерном аккаунта)
BASE_ACTION_WEIGHTS = {
    "scroll_feed": 30,
    "like_post": 20,
    "view_stories": 15,
    "follow_user": 8,
    "comment_post": 5,
    "browse_hashtag": 12,
    "view_explore": 10,
}


class WarmupAction(str, Enum):
    """Типы действий при прогреве."""
    SCROLL_FEED = "scroll_feed"
    LIKE_POST = "like_post"
    VIEW_STORIES = "view_stories"
    FOLLOW_USER = "follow_user"
    COMMENT_POST = "comment_post"
    BROWSE_HASHTAG = "browse_hashtag"
    VIEW_EXPLORE = "view_explore"


# ═══════════════════════════════════════════════════════════════
# Пуассоновские задержки
# ═══════════════════════════════════════════════════════════════


def poisson_delay(lam: float = POISSON_LAMBDA, rng: Optional[random.Random] = None) -> float:
    """
    Сгенерировать задержку по распределению Пуассона.
    lambda=1.5, ограничение 0.5-4.0 секунды.
    Экспоненциальное распределение (inter-arrival time для Пуассона).
    """
    generator = rng or random
    # Экспоненциальное распределение — межсобытийное время Пуассоновского процесса
    delay = generator.expovariate(lam)
    return max(DELAY_MIN, min(delay, DELAY_MAX))


# ═══════════════════════════════════════════════════════════════
# Уникальные паттерны по аккаунту
# ═══════════════════════════════════════════════════════════════


class AccountPattern:
    """
    Уникальный поведенческий паттерн аккаунта.
    seed = account_id → детерминированный, но уникальный набор весов,
    предпочтений по хештегам, времени активности и т.д.
    """

    def __init__(self, account_id: UUID):
        # Детерминированный seed из account_id
        seed_bytes = account_id.bytes
        self._seed = int.from_bytes(hashlib.sha256(seed_bytes).digest()[:8], "big")
        self._rng = random.Random(self._seed)

        # Модифицированные веса действий для этого аккаунта
        self.action_weights = self._generate_action_weights()

        # Предпочтительные хештеги (seed-зависимые)
        self.preferred_hashtags = self._generate_hashtag_preferences()

        # Время активности (часы UTC, когда аккаунт «бодрствует»)
        self.active_hours = self._generate_active_hours()

        # Персональный коэффициент скорости (0.7 - 1.3)
        self.speed_multiplier = self._rng.uniform(0.7, 1.3)

        # Вероятность пропуска действия (имитация «рассеянности»)
        self.skip_probability = self._rng.uniform(0.02, 0.1)

    def _generate_action_weights(self) -> Dict[str, float]:
        """Сгенерировать индивидуальные веса действий."""
        weights = {}
        for action, base_weight in BASE_ACTION_WEIGHTS.items():
            # Варьируем базовый вес ±40%
            modifier = self._rng.uniform(0.6, 1.4)
            weights[action] = base_weight * modifier
        return weights

    def _generate_hashtag_preferences(self) -> List[str]:
        """Сгенерировать набор предпочтительных хештегов."""
        all_categories = [
            ["lifestyle", "fashion", "ootd", "style"],
            ["fitness", "gym", "workout", "health"],
            ["travel", "wanderlust", "adventure", "explore"],
            ["food", "foodie", "cooking", "recipe"],
            ["photography", "photooftheday", "nature", "landscape"],
            ["beauty", "makeup", "skincare", "selfcare"],
            ["music", "art", "creative", "design"],
            ["motivation", "success", "mindset", "goals"],
        ]
        # Каждый аккаунт «интересуется» 2-4 категориями
        num_categories = self._rng.randint(2, 4)
        chosen = self._rng.sample(all_categories, k=min(num_categories, len(all_categories)))
        hashtags = []
        for category in chosen:
            hashtags.extend(category)
        return hashtags

    def _generate_active_hours(self) -> List[int]:
        """Сгенерировать часы активности (UTC)."""
        # «Просыпается» в 6-10 утра, «засыпает» в 22-02 ночи
        wake_hour = self._rng.randint(6, 10)
        sleep_hour = self._rng.randint(22, 26) % 24
        if wake_hour < sleep_hour:
            return list(range(wake_hour, sleep_hour))
        else:
            return list(range(wake_hour, 24)) + list(range(0, sleep_hour))

    def choose_action(self) -> WarmupAction:
        """Выбрать следующее действие на основе индивидуальных весов."""
        actions = list(self.action_weights.keys())
        weights = [self.action_weights[a] for a in actions]
        chosen = self._rng.choices(actions, weights=weights, k=1)[0]
        return WarmupAction(chosen)

    def get_delay(self) -> float:
        """Получить задержку с учётом персональной скорости."""
        base = poisson_delay(POISSON_LAMBDA, self._rng)
        return base * self.speed_multiplier

    def is_active_now(self) -> bool:
        """Проверить, «бодрствует» ли аккаунт сейчас."""
        current_hour = datetime.utcnow().hour
        return current_hour in self.active_hours

    def should_skip(self) -> bool:
        """Случайный пропуск действия для естественности."""
        return self._rng.random() < self.skip_probability


# ═══════════════════════════════════════════════════════════════
# Адаптивный коэффициент прогрева
# ═══════════════════════════════════════════════════════════════


class AdaptiveCoefficientManager:
    """
    Адаптивный коэффициент прогрева.
    warmup_coefficient = min(1, active_devices / 50)
    Обновляется в Redis каждые 60 секунд.
    Чем больше устройств онлайн, тем интенсивнее прогрев.
    """

    def __init__(self):
        self._last_update: float = 0.0
        self._cached_value: float = 0.0

    async def get_coefficient(self, db: Optional[AsyncSession] = None) -> float:
        """
        Получить текущий коэффициент.
        Если прошло больше COEFFICIENT_UPDATE_INTERVAL — пересчитать.
        """
        now = time.monotonic()
        if now - self._last_update >= COEFFICIENT_UPDATE_INTERVAL:
            await self._recalculate(db)
            self._last_update = now
        return self._cached_value

    async def _recalculate(self, db: Optional[AsyncSession] = None) -> None:
        """Пересчитать коэффициент по количеству активных устройств."""
        try:
            if db is not None:
                active_count = await self._count_active_devices(db)
            else:
                async with async_session_factory() as session:
                    active_count = await self._count_active_devices(session)

            coefficient = min(1.0, active_count / 50.0)
            self._cached_value = coefficient

            # Сохранить в Redis для доступа из других процессов
            await redis_client.set_warmup_coefficient(coefficient)

            await logger.ainfo(
                "warmup_coefficient_updated",
                active_devices=active_count,
                coefficient=coefficient,
            )
        except Exception as exc:
            await logger.aerror("warmup_coefficient_error", error=str(exc))
            # Попробовать прочитать предыдущее значение из Redis
            try:
                self._cached_value = await redis_client.get_warmup_coefficient()
            except Exception:
                self._cached_value = 0.0

    @staticmethod
    async def _count_active_devices(db: AsyncSession) -> int:
        """Подсчитать устройства в статусе online."""
        result = await db.execute(
            select(func.count(Device.id)).where(Device.status == "online")
        )
        return result.scalar() or 0


# ═══════════════════════════════════════════════════════════════
# Статистика прогрева в Redis
# ═══════════════════════════════════════════════════════════════


class WarmupStatsTracker:
    """
    Хранение и обновление статистики прогрева в Redis.
    Структура: hash chimera:warmup:stats:{account_id}
      - total_actions: int
      - likes: int
      - follows: int
      - comments: int
      - scrolls: int
      - hashtag_views: int
      - explore_views: int
      - story_views: int
      - session_count: int
      - last_action_at: ISO timestamp
      - total_duration_sec: float
    """

    @staticmethod
    async def increment_action(account_id: UUID, action: WarmupAction) -> None:
        """Инкрементировать счётчик действия."""
        key = f"{WARMUP_STATS_PREFIX}:{account_id}"

        # Маппинг действий → полей статистики
        field_map = {
            WarmupAction.LIKE_POST: "likes",
            WarmupAction.FOLLOW_USER: "follows",
            WarmupAction.COMMENT_POST: "comments",
            WarmupAction.SCROLL_FEED: "scrolls",
            WarmupAction.BROWSE_HASHTAG: "hashtag_views",
            WarmupAction.VIEW_EXPLORE: "explore_views",
            WarmupAction.VIEW_STORIES: "story_views",
        }

        field = field_map.get(action, "other")

        # Атомарный инкремент
        await redis_client.redis.hincrby(key, field, 1)
        await redis_client.redis.hincrby(key, "total_actions", 1)
        await redis_client.redis.hset(key, "last_action_at", datetime.utcnow().isoformat())

    @staticmethod
    async def start_session(account_id: UUID) -> str:
        """Начать сессию прогрева, вернуть session_id."""
        session_id = uuid.uuid4().hex
        session_key = f"{WARMUP_SESSION_PREFIX}:{account_id}:{session_id}"
        await redis_client.set_cache(
            session_key,
            {"started_at": datetime.utcnow().isoformat(), "actions": 0},
            ttl=7200,  # Session TTL: 2 hours
        )
        # Инкрементировать общий счётчик сессий
        stats_key = f"{WARMUP_STATS_PREFIX}:{account_id}"
        await redis_client.redis.hincrby(stats_key, "session_count", 1)
        return session_id

    @staticmethod
    async def end_session(account_id: UUID, session_id: str, duration_sec: float) -> None:
        """Завершить сессию прогрева."""
        session_key = f"{WARMUP_SESSION_PREFIX}:{account_id}:{session_id}"
        await redis_client.delete_cache(session_key)

        stats_key = f"{WARMUP_STATS_PREFIX}:{account_id}"
        await redis_client.redis.hincrbyfloat(stats_key, "total_duration_sec", duration_sec)

    @staticmethod
    async def get_stats(account_id: UUID) -> Dict[str, Any]:
        """Получить полную статистику прогрева аккаунта."""
        key = f"{WARMUP_STATS_PREFIX}:{account_id}"
        raw = await redis_client.hgetall(key)
        return {
            "total_actions": int(raw.get("total_actions", 0)),
            "likes": int(raw.get("likes", 0)),
            "follows": int(raw.get("follows", 0)),
            "comments": int(raw.get("comments", 0)),
            "scrolls": int(raw.get("scrolls", 0)),
            "hashtag_views": int(raw.get("hashtag_views", 0)),
            "explore_views": int(raw.get("explore_views", 0)),
            "story_views": int(raw.get("story_views", 0)),
            "session_count": int(raw.get("session_count", 0)),
            "last_action_at": raw.get("last_action_at"),
            "total_duration_sec": float(raw.get("total_duration_sec", 0)),
        }


# ═══════════════════════════════════════════════════════════════
# Основной движок прогрева
# ═══════════════════════════════════════════════════════════════


class ADBExecutor:
    """Прямое выполнение ADB-команд на устройстве."""

    def __init__(self, serial: str):
        self.serial = serial
        self.w, self.h = 1080, 2400
        self._detect_screen_size()

    def _detect_screen_size(self):
        try:
            out = self._shell("wm size")
            if ":" in out:
                w, h = out.split(":")[1].strip().split("x")
                self.w, self.h = int(w), int(h)
        except Exception:
            pass

    def _shell(self, cmd: str) -> str:
        r = subprocess.run(
            ["adb", "-s", self.serial, "shell", cmd],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip()

    def tap(self, x: int, y: int):
        self._shell(f"input tap {x} {y}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300):
        self._shell(f"input swipe {x1} {y1} {x2} {y2} {duration}")

    def do_scroll(self):
        sx = self.w // 2 + random.randint(-40, 40)
        sy = int(self.h * 0.7) + random.randint(-30, 30)
        ey = int(self.h * 0.3) + random.randint(-50, 50)
        dur = random.randint(200, 500)
        self.swipe(sx, sy, sx + random.randint(-8, 8), ey, dur)
        time.sleep(random.uniform(1.5, 4))

    def do_like(self) -> bool:
        cx = self.w // 2 + random.randint(-80, 80)
        cy = self.h // 2 + random.randint(-100, 50)
        self.tap(cx, cy)
        time.sleep(0.12)
        self.tap(cx + random.randint(-3, 3), cy + random.randint(-3, 3))
        time.sleep(1)
        return True

    def do_follow(self) -> bool:
        from app.services.ui_finder import UIFinder
        ui = UIFinder(self.serial)
        btn = ui.find_any([
            {"text": "Follow"}, {"text": "Подписаться"},
            {"text_contains": "follow"},
        ])
        if btn:
            self.tap(btn["x"], btn["y"])
            time.sleep(random.uniform(1, 2))
            return True
        return False

    def do_view_story(self):
        x = random.randint(30, min(200, self.w - 30))
        y = random.randint(60, 130)
        self.tap(x, y)
        time.sleep(random.uniform(3, 7))
        self._shell("input keyevent 4")
        time.sleep(1)


class WarmupEngine:
    """
    Основной движок прогрева аккаунтов.
    Для каждого аккаунта создаёт уникальный паттерн поведения,
    выполняет действия с задержками по пуассоновскому распределению,
    учитывает адаптивный коэффициент нагрузки.
    Поддерживает прямое ADB-выполнение на устройстве.
    """

    def __init__(self):
        self._coefficient_mgr = AdaptiveCoefficientManager()
        self._stats = WarmupStatsTracker()
        self._running_sessions: Dict[UUID, bool] = {}
        self._adb_executors: Dict[str, ADBExecutor] = {}

    async def start_warmup(
        self,
        db: AsyncSession,
        account_id: UUID,
        duration_minutes: int = 30,
        max_actions: int = 100,
    ) -> Dict[str, Any]:
        """
        Запустить сессию прогрева для аккаунта.
        duration_minutes — максимальная длительность сессии.
        max_actions — максимальное число действий за сессию.
        """
        # Проверить, не идёт ли уже прогрев этого аккаунта
        if self._running_sessions.get(account_id):
            await logger.awarning("warmup_already_running", account_id=str(account_id))
            return {"status": "already_running", "account_id": str(account_id)}

        # Проверить что аккаунт существует и прогрев включён
        result = await db.execute(
            select(SocialAccount).where(
                SocialAccount.id == account_id,
                SocialAccount.warmup_enabled.is_(True),
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            await logger.awarning("warmup_account_not_found_or_disabled", account_id=str(account_id))
            return {"status": "not_found_or_disabled", "account_id": str(account_id)}

        # Создать паттерн и начать сессию
        pattern = AccountPattern(account_id)

        if not pattern.is_active_now():
            await logger.ainfo("warmup_outside_active_hours", account_id=str(account_id))
            return {"status": "outside_active_hours", "account_id": str(account_id)}

        session_id = await self._stats.start_session(account_id)
        self._running_sessions[account_id] = True

        session_result = await self._run_session(
            db=db,
            account=account,
            pattern=pattern,
            session_id=session_id,
            duration_minutes=duration_minutes,
            max_actions=max_actions,
        )

        return session_result

    async def _run_session(
        self,
        db: AsyncSession,
        account: SocialAccount,
        pattern: AccountPattern,
        session_id: str,
        duration_minutes: int,
        max_actions: int,
    ) -> Dict[str, Any]:
        """
        Выполнить сессию прогрева: циклически выбирать действия,
        выполнять с задержками, учитывать коэффициент.
        """
        account_id = account.id
        start_time = time.monotonic()
        deadline = start_time + (duration_minutes * 60)
        actions_done = 0
        errors = 0

        try:
            while (
                time.monotonic() < deadline
                and actions_done < max_actions
                and self._running_sessions.get(account_id, False)
            ):
                # Получить адаптивный коэффициент
                coefficient = await self._coefficient_mgr.get_coefficient(db)

                # Если коэффициент слишком низкий — замедлить
                if coefficient < 0.1:
                    await asyncio.sleep(10.0)
                    continue

                # Пропуск действия для естественности
                if pattern.should_skip():
                    delay = pattern.get_delay() * 2
                    await asyncio.sleep(delay)
                    continue

                # Выбрать действие
                action = pattern.choose_action()

                # Создать задачу на выполнение действия на устройстве
                try:
                    await self._execute_action(db, account, action, pattern)
                    actions_done += 1
                    await self._stats.increment_action(account_id, action)
                except Exception as exc:
                    errors += 1
                    await logger.aerror(
                        "warmup_action_error",
                        account_id=str(account_id),
                        action=action.value,
                        error=str(exc),
                    )
                    if errors > 10:
                        await logger.aerror("warmup_too_many_errors", account_id=str(account_id))
                        break

                # Пуассоновская задержка с учётом коэффициента
                delay = pattern.get_delay()
                adjusted_delay = delay / max(coefficient, 0.1)
                adjusted_delay = max(DELAY_MIN, min(adjusted_delay, DELAY_MAX * 3))
                await asyncio.sleep(adjusted_delay)

        finally:
            duration = time.monotonic() - start_time
            self._running_sessions.pop(account_id, None)
            await self._stats.end_session(account_id, session_id, duration)

            # Обновить last_activity_at аккаунта
            await db.execute(
                update(SocialAccount)
                .where(SocialAccount.id == account_id)
                .values(last_activity_at=datetime.utcnow())
            )
            await db.flush()

        result = {
            "status": "completed",
            "account_id": str(account_id),
            "session_id": session_id,
            "actions_done": actions_done,
            "errors": errors,
            "duration_sec": round(duration, 1),
        }

        await logger.ainfo("warmup_session_completed", **result)
        return result

    async def _execute_action(
        self,
        db: AsyncSession,
        account: SocialAccount,
        action: WarmupAction,
        pattern: AccountPattern,
    ) -> None:
        """
        Создать задачу на устройстве для выполнения действия прогрева.
        Задача отправляется через Redis Stream, агент на устройстве выполняет
        её с помощью human_input для имитации человеческого взаимодействия.
        """
        # Построить payload в зависимости от типа действия
        payload = self._build_action_payload(action, pattern)

        task = Task(
            id=uuid.uuid4(),
            user_id=account.user_id,
            device_id=account.device_id,
            account_id=account.id,
            task_type=f"warmup_{action.value}",
            status="pending",
            priority=3,  # Прогрев — низкий приоритет
            payload=payload,
            created_at=datetime.utcnow(),
        )
        db.add(task)
        await db.flush()

        # Отправить в Redis Stream
        await redis_client.add_task(
            "chimera:tasks:warmup",
            {
                "task_id": str(task.id),
                "device_id": str(account.device_id) if account.device_id else None,
                "account_id": str(account.id),
                "action": action.value,
                "payload": payload,
            },
        )

        # Записать лог действия
        log_entry = ActionLog(
            device_id=account.device_id,
            account_id=account.id,
            action_type=f"warmup_{action.value}",
            details={"task_id": str(task.id)},
            success=True,
            created_at=datetime.utcnow(),
        )
        db.add(log_entry)
        await db.flush()

    @staticmethod
    def _build_action_payload(action: WarmupAction, pattern: AccountPattern) -> Dict[str, Any]:
        """Построить payload действия с параметрами для агента на устройстве."""
        rng = random.Random(pattern._seed + hash(action.value))

        if action == WarmupAction.SCROLL_FEED:
            return {
                "action": "scroll_feed",
                "scroll_count": rng.randint(3, 12),
                "pause_on_post_probability": rng.uniform(0.2, 0.5),
                "use_human_cursor": True,
            }

        elif action == WarmupAction.LIKE_POST:
            return {
                "action": "like_post",
                "double_tap": rng.random() > 0.3,  # 70% double-tap, 30% button
                "use_human_cursor": True,
            }

        elif action == WarmupAction.VIEW_STORIES:
            return {
                "action": "view_stories",
                "story_count": rng.randint(1, 5),
                "watch_duration_sec": rng.uniform(2.0, 8.0),
                "skip_probability": rng.uniform(0.1, 0.4),
                "use_human_cursor": True,
            }

        elif action == WarmupAction.FOLLOW_USER:
            return {
                "action": "follow_user",
                "from_explore": rng.random() > 0.5,
                "use_human_cursor": True,
            }

        elif action == WarmupAction.COMMENT_POST:
            # Простые комментарии для прогрева
            comments = ["🔥", "❤️", "👍", "Nice!", "Cool!", "😍", "Wow", "Amazing"]
            return {
                "action": "comment_post",
                "comment_text": rng.choice(comments),
                "use_human_cursor": True,
            }

        elif action == WarmupAction.BROWSE_HASHTAG:
            hashtag = rng.choice(pattern.preferred_hashtags)
            return {
                "action": "browse_hashtag",
                "hashtag": hashtag,
                "scroll_count": rng.randint(3, 8),
                "like_probability": rng.uniform(0.1, 0.3),
                "use_human_cursor": True,
            }

        elif action == WarmupAction.VIEW_EXPLORE:
            return {
                "action": "view_explore",
                "scroll_count": rng.randint(2, 6),
                "tap_post_probability": rng.uniform(0.2, 0.4),
                "use_human_cursor": True,
            }

        return {"action": action.value, "use_human_cursor": True}

    async def stop_warmup(self, account_id: UUID) -> bool:
        """Остановить текущую сессию прогрева аккаунта."""
        if account_id in self._running_sessions:
            self._running_sessions[account_id] = False
            await logger.ainfo("warmup_stopped", account_id=str(account_id))
            return True
        return False

    async def get_account_stats(self, account_id: UUID) -> Dict[str, Any]:
        """Получить статистику прогрева аккаунта."""
        return await self._stats.get_stats(account_id)

    async def start_bulk_warmup(
        self,
        db: AsyncSession,
        user_id: UUID,
        duration_minutes: int = 30,
        max_actions_per_account: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Запустить прогрев для всех аккаунтов пользователя с warmup_enabled=True.
        Запускает сессии параллельно.
        """
        result = await db.execute(
            select(SocialAccount).where(
                SocialAccount.user_id == user_id,
                SocialAccount.warmup_enabled.is_(True),
                SocialAccount.status == "active",
            )
        )
        accounts = result.scalars().all()

        if not accounts:
            await logger.ainfo("bulk_warmup_no_accounts", user_id=str(user_id))
            return []

        await logger.ainfo(
            "bulk_warmup_starting",
            user_id=str(user_id),
            accounts_count=len(accounts),
        )

        # Запустить прогрев для каждого аккаунта конкурентно
        tasks = [
            self.start_warmup(db, account.id, duration_minutes, max_actions_per_account)
            for account in accounts
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        completed_results = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                completed_results.append({
                    "status": "error",
                    "account_id": str(accounts[i].id),
                    "error": str(res),
                })
            else:
                completed_results.append(res)

        return completed_results

    async def get_warmup_coefficient(self, db: Optional[AsyncSession] = None) -> float:
        """Получить текущий адаптивный коэффициент."""
        return await self._coefficient_mgr.get_coefficient(db)

    async def run_direct(
        self,
        serial: str,
        duration_sec: int = 300,
    ) -> Dict[str, Any]:
        """
        Прямой прогрев через ADB — реальное выполнение на телефоне.
        Использует HumanCursor для реалистичного движения курсора.
        """
        from app.services.human_cursor import HumanCursor

        if serial not in self._adb_executors:
            self._adb_executors[serial] = ADBExecutor(serial)
        adb = self._adb_executors[serial]
        cursor = HumanCursor(serial, adb.w, adb.h)

        results = {
            "likes": 0, "scrolls": 0, "follows": 0,
            "stories": 0, "errors": 0, "elapsed": 0,
        }
        start = time.time()
        end = start + duration_sec

        while time.time() < end:
            results["elapsed"] = int(time.time() - start)

            action = random.choices(
                ["scroll", "like", "follow", "story", "pause"],
                weights=[35, 25, 10, 10, 20], k=1,
            )[0]

            try:
                if action == "scroll":
                    cursor.scroll_feed(random.choice(["soft", "medium", "hard"]))
                    results["scrolls"] += 1
                    await asyncio.sleep(random.uniform(1.5, 4))

                elif action == "like":
                    cx = adb.w // 2 + random.randint(-100, 100)
                    cy = adb.h // 2 + random.randint(-80, 60)
                    cursor.tap(cx, cy)
                    time.sleep(0.12)
                    adb._shell(f"input tap {cx + random.randint(-3, 3)} {cy + random.randint(-3, 3)}")
                    results["likes"] += 1
                    await asyncio.sleep(random.uniform(1, 3))
                    cursor.scroll_feed("medium")

                elif action == "follow":
                    from app.services.ui_finder import UIFinder
                    ui = UIFinder(serial)
                    btn = ui.find_any([{"text": "Follow"}, {"text": "Подписаться"}])
                    if btn:
                        cursor.tap(btn["x"], btn["y"])
                        results["follows"] += 1
                    await asyncio.sleep(random.uniform(1, 3))

                elif action == "story":
                    x = random.randint(30, min(200, adb.w - 30))
                    cursor.tap(x, random.randint(60, 130))
                    results["stories"] += 1
                    await asyncio.sleep(random.uniform(3, 7))
                    adb._shell("input keyevent 4")
                    await asyncio.sleep(1)

                elif action == "pause":
                    await asyncio.sleep(random.uniform(5, 20))

            except Exception as e:
                await logger.aerror("warmup_direct_error", error=str(e))
                results["errors"] += 1

            delay = min(4.0, max(0.5, random.expovariate(1.5)))
            await asyncio.sleep(delay)

        results["elapsed"] = int(time.time() - start)
        return results

    async def cross_account_warmup(self, serial: str, accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Кросс-прогрев: аккаунты одной платформы «дружат».
        A лайкает посты B, B комментирует A.
        """
        from app.services.human_cursor import HumanCursor

        if serial not in self._adb_executors:
            self._adb_executors[serial] = ADBExecutor(serial)
        adb = self._adb_executors[serial]
        cursor = HumanCursor(serial, adb.w, adb.h)

        interactions = 0
        for i, acc_a in enumerate(accounts):
            for acc_b in accounts[i + 1:]:
                try:
                    await logger.ainfo(
                        "cross_warmup",
                        a=acc_a.get("username"), b=acc_b.get("username"),
                    )
                    username_b = acc_b["username"]
                    adb._shell(
                        f"am start -a android.intent.action.VIEW "
                        f"-d 'instagram://user?username={username_b}'"
                    )
                    await asyncio.sleep(3)
                    cursor.tap(adb.w // 3, adb.h // 2)
                    await asyncio.sleep(1)
                    cx, cy = adb.w // 2, adb.h // 2
                    adb._shell(f"input tap {cx} {cy}")
                    time.sleep(0.12)
                    adb._shell(f"input tap {cx} {cy}")
                    await asyncio.sleep(2)
                    adb._shell("input keyevent 4")
                    await asyncio.sleep(1)
                    adb._shell("input keyevent 4")
                    interactions += 1
                    await asyncio.sleep(random.uniform(3, 8))
                except Exception as e:
                    await logger.aerror("cross_warmup_error", error=str(e))

        return {"interactions": interactions, "accounts": len(accounts)}
