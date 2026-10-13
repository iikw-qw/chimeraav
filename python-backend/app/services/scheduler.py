"""Chimera scheduler — APScheduler + ML time optimizer + DLQ + Poisson delays."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models.post import Post
from app.models.task import Task

try:
    from sklearn.ensemble import GradientBoostingRegressor  # type: ignore
except Exception:  # pragma: no cover - optional dep
    GradientBoostingRegressor = None  # type: ignore


_PLATFORM_IDX: dict[str, int] = {}


def _platform_code(name: str) -> int:
    if name not in _PLATFORM_IDX:
        _PLATFORM_IDX[name] = len(_PLATFORM_IDX)
    return _PLATFORM_IDX[name]


class TimeOptimizer:
    """Predict best posting time from historical engagement."""

    def __init__(self) -> None:
        self._model: Any = None

    async def train(self) -> bool:
        if GradientBoostingRegressor is None:
            return False

        async with SessionLocal() as session:
            stmt = select(Post).where(Post.published_at.is_not(None))
            posts = list((await session.execute(stmt)).scalars().all())

        rows: list[tuple[int, int, int, float]] = []
        for p in posts:
            if p.published_at is None:
                continue
            rate = 0.0
            if isinstance(p.engagement_metrics, dict):
                rate = float(p.engagement_metrics.get("engagement_rate") or 0.0)
            rows.append(
                (
                    p.published_at.hour,
                    p.published_at.weekday(),
                    _platform_code(p.platform),
                    rate,
                )
            )
        if len(rows) < 8:
            return False

        X = np.array([[r[0], r[1], r[2]] for r in rows], dtype=float)
        y = np.array([r[3] for r in rows], dtype=float)
        model = GradientBoostingRegressor(n_estimators=80, max_depth=3)
        model.fit(X, y)
        self._model = model
        return True

    def predict_best_time(self, platform: str, day_of_week: int | None = None) -> int:
        if self._model is None:
            return 19
        code = _platform_code(platform)
        dow = day_of_week if day_of_week is not None else datetime.now().weekday()
        X = np.array([[h, dow, code] for h in range(24)], dtype=float)
        preds = self._model.predict(X)
        return int(np.argmax(preds))


class ChimeraScheduler:
    """APScheduler wrapper with Poisson-spaced jobs and DLQ promotion."""

    def __init__(self) -> None:
        db_path = Path(settings.data_dir) / "chimera.db"
        self._scheduler = AsyncIOScheduler(
            jobstores={
                "default": SQLAlchemyJobStore(
                    url=f"sqlite:///{db_path.as_posix()}"
                )
            }
        )
        self.time_optimizer = TimeOptimizer()
        self._dlq_callbacks: list[Any] = []

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
            self._scheduler.add_job(
                self._check_dlq, "interval", seconds=30, id="chimera:dlq-sweep",
                replace_existing=True,
            )

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    @property
    def raw(self) -> AsyncIOScheduler:
        return self._scheduler

    @staticmethod
    def poisson_delay() -> float:
        """Exponential-distributed delay capped to 0.5–4s."""
        value = float(np.random.exponential(2.0))
        return float(min(4.0, max(0.5, value)))

    def on_dlq(self, callback: Any) -> None:
        self._dlq_callbacks.append(callback)

    async def _check_dlq(self) -> None:
        async with SessionLocal() as session:
            stmt = select(Task).where(
                Task.status.in_(("failed", "running")),
                Task.retry_count >= Task.max_retries,
            )
            rows = list((await session.execute(stmt)).scalars().all())
            promoted: list[Task] = []
            for task in rows:
                if task.status == "dlq":
                    continue
                task.status = "dlq"
                task.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                promoted.append(task)
            if promoted:
                await session.commit()

        for task in promoted:
            if task.error_message and "locator" in task.error_message.lower():
                await self._retrain_ui_analyzer(task)
            for cb in self._dlq_callbacks:
                try:
                    await cb(task)
                except Exception:
                    pass

    async def _retrain_ui_analyzer(self, task: Task) -> None:
        try:
            from app.services.ui_analyzer import ui_analyzer

            await ui_analyzer.retrain_from_failure(task)
        except Exception:
            pass


chimera_scheduler = ChimeraScheduler()


async def poisson_sleep() -> None:
    await asyncio.sleep(ChimeraScheduler.poisson_delay())
