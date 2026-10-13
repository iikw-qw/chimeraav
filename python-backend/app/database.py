"""Async SQLAlchemy engine + session factory tuned for SQLite."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


DB_PATH = Path(settings.data_dir) / "chimera.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH.as_posix()}"


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"timeout": 5},
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-64000")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


_DEFAULT_TEMPLATES: tuple[tuple[str, str, str, str], ...] = (
    ("Friendly Hello", "welcome", "Hi, how are you?", "en"),
    ("Casual Hey", "welcome", "Hey! How's it going?", "en"),
    ("Warm Hello", "welcome", "Hello! How are you doing today?", "en"),
    ("Nice Meet", "welcome", "Hi there! Nice to meet you!", "en"),
)


async def _seed_message_templates() -> None:
    from app.models.message_template import MessageTemplate

    async with SessionLocal() as session:
        existing = await session.scalar(select(func.count()).select_from(MessageTemplate))
        if existing and existing > 0:
            return
        session.add_all(
            [
                MessageTemplate(
                    name=name, style=style, template_text=text, language=lang
                )
                for name, style, text, lang in _DEFAULT_TEMPLATES
            ]
        )
        await session.commit()


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Import models so they register with Base.metadata before create_all.
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _migrate_unique_codes()
    await _migrate_email_columns()
    await _seed_message_templates()
    await _seed_caption_templates()


async def _migrate_unique_codes() -> None:
    """Add `unique_code` column to legacy devices/accounts tables and backfill
    every row with a freshly generated unique code. Idempotent."""
    from sqlalchemy import text

    from app.models._common import gen_account_code, gen_device_code

    async with engine.begin() as conn:
        # devices.unique_code
        cols = await conn.execute(text("PRAGMA table_info(devices)"))
        if "unique_code" not in {r[1] for r in cols.fetchall()}:
            await conn.execute(text("ALTER TABLE devices ADD COLUMN unique_code VARCHAR(24)"))
        # accounts.unique_code
        cols = await conn.execute(text("PRAGMA table_info(accounts)"))
        if "unique_code" not in {r[1] for r in cols.fetchall()}:
            await conn.execute(text("ALTER TABLE accounts ADD COLUMN unique_code VARCHAR(24)"))

    async with SessionLocal() as session:
        # Backfill devices missing a code
        rows = (
            await session.execute(text("SELECT id FROM devices WHERE unique_code IS NULL OR unique_code = ''"))
        ).fetchall()
        for (rid,) in rows:
            # retry on the (extremely unlikely) collision
            for _ in range(5):
                code = gen_device_code()
                exists = (
                    await session.execute(
                        text("SELECT 1 FROM devices WHERE unique_code = :c"), {"c": code}
                    )
                ).scalar_one_or_none()
                if exists is None:
                    break
            await session.execute(
                text("UPDATE devices SET unique_code = :c WHERE id = :id"),
                {"c": code, "id": rid},
            )
        rows = (
            await session.execute(text("SELECT id FROM accounts WHERE unique_code IS NULL OR unique_code = ''"))
        ).fetchall()
        for (rid,) in rows:
            for _ in range(5):
                code = gen_account_code()
                exists = (
                    await session.execute(
                        text("SELECT 1 FROM accounts WHERE unique_code = :c"), {"c": code}
                    )
                ).scalar_one_or_none()
                if exists is None:
                    break
            await session.execute(
                text("UPDATE accounts SET unique_code = :c WHERE id = :id"),
                {"c": code, "id": rid},
            )
        await session.commit()

    # Ensure UNIQUE indexes exist (create_all on a new install handles this via
    # the column's `unique=True`, but legacy tables that grew the column via
    # ALTER TABLE need the index added explicitly).
    async with engine.begin() as conn:
        await conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ux_devices_unique_code ON devices(unique_code)")
        )
        await conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ux_accounts_unique_code ON accounts(unique_code)")
        )


_DEFAULT_CAPTIONS: list[tuple[str, str, str, str]] = [
    ("Living my best life", "lifestyle", "instagram", "en"),
    ("New day, new adventures", "lifestyle", "instagram", "en"),
    ("Making memories", "general", "instagram", "en"),
    ("Good vibes only", "mood", "instagram", "en"),
    ("Chase your dreams", "motivation", "instagram", "en"),
    ("Weekend mood", "mood", "instagram", "en"),
    ("Life is beautiful", "lifestyle", "instagram", "en"),
    ("Stay positive", "motivation", "instagram", "en"),
    ("Explore more", "travel", "instagram", "en"),
    ("Coffee and chill", "mood", "instagram", "en"),
    ("Sunshine state of mind", "mood", "instagram", "en"),
    ("Creating my own sunshine", "motivation", "instagram", "en"),
    ("Less is more", "lifestyle", "instagram", "en"),
    ("Simple pleasures", "lifestyle", "instagram", "en"),
    ("Grateful for this moment", "mood", "instagram", "en"),
    ("Adventure awaits", "travel", "instagram", "en"),
    ("Just breathe", "motivation", "instagram", "en"),
    ("Let it be", "mood", "instagram", "en"),
    ("Feeling fabulous", "mood", "instagram", "en"),
    ("Today was a good day", "lifestyle", "instagram", "en"),
    ("The best is yet to come", "motivation", "tiktok", "en"),
    ("Vibe check", "mood", "tiktok", "en"),
    ("Watch till the end", "general", "tiktok", "en"),
    ("POV: you found the best page", "general", "tiktok", "en"),
    ("This hits different", "mood", "tiktok", "en"),
    ("Wait for it", "general", "tiktok", "en"),
    ("No caption needed", "general", "facebook", "en"),
    ("Blessed and grateful", "mood", "facebook", "en"),
    ("Throwback to this", "general", "facebook", "en"),
    ("Sharing some love today", "mood", "facebook", "en"),
    ("Thoughts?", "general", "twitter", "en"),
    ("Thread below", "general", "twitter", "en"),
    ("Hot take:", "general", "twitter", "en"),
]


async def _seed_caption_templates() -> None:
    from app.models.caption_template import CaptionTemplate

    async with SessionLocal() as session:
        existing = await session.scalar(select(func.count()).select_from(CaptionTemplate))
        if existing and existing > 0:
            return
        session.add_all(
            [
                CaptionTemplate(text=text, category=cat, platform=plat, language=lang)
                for text, cat, plat, lang in _DEFAULT_CAPTIONS
            ]
        )
        await session.commit()


async def _migrate_email_columns() -> None:
    """Add email-related columns to accounts table. Idempotent."""
    from sqlalchemy import text

    async with engine.begin() as conn:
        cols = await conn.execute(text("PRAGMA table_info(accounts)"))
        existing = {r[1] for r in cols.fetchall()}
        if "email" not in existing:
            await conn.execute(
                text("ALTER TABLE accounts ADD COLUMN email VARCHAR(200)")
            )
        if "email_password_encrypted" not in existing:
            await conn.execute(
                text("ALTER TABLE accounts ADD COLUMN email_password_encrypted TEXT")
            )
        if "email_imap_server" not in existing:
            await conn.execute(
                text("ALTER TABLE accounts ADD COLUMN email_imap_server VARCHAR(100)")
            )


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
