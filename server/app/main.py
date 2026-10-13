"""
Главный файл FastAPI-приложения Chimera v5.0.
Lifespan, CORS, роутеры, healthcheck, Prometheus.
Зависит от: config, database, redis_client, все роутеры
"""

import logging
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import engine
from app.services.redis_client import redis_client
from app.services.health_manager import health_manager
from app.services.scheduler_service import scheduler_service

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("chimera.startup", version=settings.app_version)
    await redis_client.connect()
    logger.info("redis.connected")

    await redis_client.create_consumer_group("chimera:tasks", "task_workers")

    # Запуск Health Manager и Scheduler
    await health_manager.start()
    logger.info("health_manager.started")

    await scheduler_service.start()
    logger.info("scheduler_service.started")

    import asyncio
    from app.services.hardware_auth import get_hardware_id, get_host_metrics
    from app.models.hardware import HostMetric
    from app.database import async_session_factory as _sf

    async def _collect_metrics():
        while True:
            try:
                m = get_host_metrics()
                async with _sf() as db:
                    db.add(HostMetric(hardware_id=get_hardware_id(), **m))
                    await db.commit()
            except Exception:
                pass
            await asyncio.sleep(60)

    _metrics_task = asyncio.create_task(_collect_metrics())
    logger.info("host_metrics_collector.started")

    yield

    _metrics_task.cancel()

    # Shutdown
    logger.info("chimera.shutdown")
    await scheduler_service.stop()
    await health_manager.stop()
    await redis_client.disconnect()
    await engine.dispose()


app = FastAPI(
    title="Chimera v5.0",
    description="Social media orchestration platform",
    version=settings.app_version,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)

# ═══ Import and register routers ═══
from app.api import auth, devices, accounts, tasks, posts, scheduler, streaming, settings as settings_api, notifications, analytics, logs

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(devices.router, prefix="/api/v1/devices", tags=["devices"])
app.include_router(accounts.router, prefix="/api/v1/accounts", tags=["accounts"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(posts.router, prefix="/api/v1/posts", tags=["posts"])
app.include_router(scheduler.router, prefix="/api/v1/scheduler", tags=["scheduler"])
app.include_router(streaming.router, prefix="/api/v1/streams", tags=["streaming"])
app.include_router(settings_api.router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["notifications"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(logs.router, prefix="/api/v1/logs", tags=["logs"])

# ═══ WebSocket routes ═══
from app.ws import stream_handler, viewer_handler, settings_broadcast

app.include_router(stream_handler.router)
app.include_router(viewer_handler.router)
app.include_router(settings_broadcast.router)


@app.get("/health")
async def health_check():
    db_status = "connected"
    redis_status = "connected"

    try:
        from app.database import async_session_factory
        async with async_session_factory() as session:
            await session.execute(__import__("sqlalchemy").text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    try:
        if not await redis_client.ping():
            redis_status = "disconnected"
    except Exception:
        redis_status = "disconnected"

    status = "healthy" if db_status == "connected" and redis_status == "connected" else "unhealthy"
    return {"status": status, "database": db_status, "redis": redis_status, "version": settings.app_version}
