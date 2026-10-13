"""Chimera shared Telegram bot.

ONE bot for all Chimera users. Each Chimera installation talks to the
same bot — users connect by /start <auth_code>, and the bot keeps a
mapping of telegram_user_id -> chimera_install_id in the local sqlite DB.

How it works
------------
1. Operator creates a single bot via @BotFather and pastes the token
   into the placeholder below (or sets CHIMERA_BOT_TOKEN env var).
2. Every Chimera installation runs `python chimera_bot.py` (the desktop
   app launches it automatically on startup if a token is configured).
3. End-users open the bot in Telegram, send /start <code>, and get
   notifications + post controls for *their* install.

Token placement
---------------
Edit `BOT_TOKEN` below, OR set environment variable `CHIMERA_BOT_TOKEN`.
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

import httpx

# === DUPLICATE PREVENTION ===
LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bot.lock")


def _check_single_instance() -> None:
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, old_pid)
            if handle:
                kernel32.CloseHandle(handle)
                print(f"ERROR: Bot already running (PID {old_pid}). Exiting.")
                sys.exit(1)
        except (ValueError, OSError, AttributeError):
            pass
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))


def _cleanup_lock() -> None:
    try:
        os.remove(LOCK_FILE)
    except OSError:
        pass


atexit.register(_cleanup_lock)
_check_single_instance()
# === END DUPLICATE PREVENTION ===
from sqlalchemy import Column, DateTime, String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

# ────────────────────────────────────────────────────────────────────
# 🔑  PASTE BOT TOKEN HERE  (or set env CHIMERA_BOT_TOKEN)
# ────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ["CHIMERA_BOT_TOKEN"]
# ────────────────────────────────────────────────────────────────────

API_BASE = "https://api.telegram.org"
DB_URL = os.environ.get("CHIMERA_BOT_DB", "sqlite+aiosqlite:///chimera_bot.db")
APP_API_BASE = os.environ.get("CHIMERA_APP_API", "http://127.0.0.1:17842")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [bot] %(message)s")
log = logging.getLogger("chimera-bot")

Base = declarative_base()


class BotUser(Base):
    __tablename__ = "bot_users"
    telegram_id = Column(String, primary_key=True)
    install_id = Column(String, nullable=True)         # which Chimera install
    auth_code = Column(String, nullable=True)
    role = Column(String, default="user")              # user | admin
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))


_engine = create_async_engine(DB_URL, future=True)
_Session = async_sessionmaker(_engine, expire_on_commit=False)


# ─── FAQ ────────────────────────────────────────────────────────────
FAQ: list[tuple[str, str]] = [
    (
        "Как добавить телефон в Chimera?",
        "Откройте приложение → вкладка «Телефоны» → подключите телефон по USB и"
        " активируйте отладку. Android: «Настройки → О телефоне → 7 раз нажать"
        " «Номер сборки» → Настройки разработчика → USB-отладка». iOS: установите"
        " WebDriverAgent или используйте джейлбрейк (см. встроенную инструкцию)."
        " После подключения телефон появится в сетке автоматически.",
    ),
    (
        "Как настроить прокси/VPN на телефоне?",
        "В приложении: вкладка «Настройки → Прокси». Добавьте прокси с"
        " логином/паролем и привяжите к телефону через ПКМ → «Привязать прокси»."
        " На самой карточке телефона в строке IP отобразится текущий внешний"
        " IP — так вы сразу видите, что прокси работает.",
    ),
    (
        "Что такое прогрев и зачем он нужен?",
        "Прогрев имитирует поведение реального пользователя: пролистывание ленты,"
        " лайки, заходы на профили, подписки. Это снижает шанс блокировки молодого"
        " аккаунта. Запускается во вкладке «Прогрев» — вы выбираете акк и"
        " длительность, всё остальное Chimera делает сама.",
    ),
    (
        "Как работают датасеты и SIPR?",
        "Датасет — это папка с фото и видео. SIPR (Smart Image Pool Rotator)"
        " автоматически выбирает наименее «изношенный» контент и не повторяет одни"
        " и те же тройки в соседних постах. Стратегии «smart» и «cross» —"
        " наиболее экономные по материалу.",
    ),
    (
        "Почему появляется задержка при стриме экрана?",
        "Откройте «Настройки → Демонстрация экрана» и выберите пресет «Плавность»."
        " Это самый низкий FPS-кадр и максимальное число кадров — задержка падает"
        " до уровня scrcpy/LaiXi. Если телефон через Wi-Fi — переключите на USB.",
    ),
    (
        "Что такое антидетект и как он улучшен?",
        "Chimera меняет device fingerprint, локальное время, build.prop, IMEI"
        " (на рутованных устройствах), GPS, MAC и user-agent при каждой ротации."
        " В настройках можно задать профиль (samsung/xiaomi/pixel) и интервал"
        " ротации.",
    ),
    (
        "Как запланировать постинг на неделю вперёд?",
        "Вкладка «Планировщик» → «Запланировать» → выберите датасет, платформу,"
        " количество дней и постов в день. Chimera создаст задачи и распределит"
        " их равномерно по выбранному окну часов.",
    ),
    (
        "Что делать, если телефон ушёл в offline?",
        "Сначала проверьте USB-кабель и питание. Затем в Chimera ПКМ по карточке"
        " → «Перезагрузить». Если не помогает — отсоедините и заново подключите"
        " кабель. ADB иногда теряет соединение — это лечится `adb kill-server`.",
    ),
    (
        "Чем помогает чистка метаданных?",
        "EXIF, XMP, гео-теги и серийники камеры — всё это даёт платформам"
        " связать ваши аккаунты. Chimera удаляет служебные поля и добавляет"
        " микро-перцептивные изменения (LSB, контраст), чтобы перцептивный хеш"
        " отличался от исходника.",
    ),
    (
        "Как обновить Chimera, чтобы изменения дошли до всех устройств?",
        "См. файл UPDATES.md в корне проекта. Кратко: редактор pushит обновление"
        " в общий репозиторий, приложение при запуске сверяет версию через API"
        " бота и подтягивает diff.",
    ),
]


def faq_text() -> str:
    lines = ["📚 *Частые вопросы*\n"]
    for i, (q, a) in enumerate(FAQ, 1):
        lines.append(f"*{i}. {q}*\n_{a}_\n")
    return "\n".join(lines)


# ─── Telegram API helpers ───────────────────────────────────────────
async def _api(client: httpx.AsyncClient, method: str, **payload: Any) -> dict:
    if not BOT_TOKEN or BOT_TOKEN.startswith("PASTE_"):
        raise RuntimeError("BOT_TOKEN is not configured")
    r = await client.post(
        f"{API_BASE}/bot{BOT_TOKEN}/{method}", json=payload, timeout=30.0
    )
    r.raise_for_status()
    return r.json()


async def send_text(client: httpx.AsyncClient, chat_id: str | int, text: str,
                    *, reply_markup: dict | None = None) -> None:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        await _api(client, "sendMessage", **payload)
    except Exception as exc:
        log.warning("sendMessage failed: %s", exc)


# ─── Chimera app API helpers ────────────────────────────────────────
async def fetch_devices(client: httpx.AsyncClient) -> list[dict]:
    try:
        r = await client.get(f"{APP_API_BASE}/api/devices", timeout=10.0)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.warning("fetch_devices failed: %s", exc)
        return []


async def fetch_pending_posts(client: httpx.AsyncClient) -> list[dict]:
    try:
        r = await client.get(
            f"{APP_API_BASE}/api/posts", params={"status": "draft", "limit": 20},
            timeout=10.0,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


# ─── Auth ───────────────────────────────────────────────────────────
async def auth_user(session: AsyncSession, telegram_id: str,
                    code: str | None) -> bool:
    """Bind a Telegram user to a Chimera install via the auth code."""
    if not code:
        return False
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{APP_API_BASE}/api/auth/bot-confirm",
                json={"telegram_id": telegram_id, "code": code},
                timeout=10.0,
            )
            if r.status_code != 200:
                return False
            data = r.json()
    except Exception as exc:
        log.warning("auth check failed: %s", exc)
        return False

    install_id = data.get("install_id")
    if not install_id:
        return False

    user = await session.get(BotUser, telegram_id)
    if user is None:
        user = BotUser(telegram_id=telegram_id, install_id=install_id, auth_code=code)
        session.add(user)
    else:
        user.install_id = install_id
        user.auth_code = code
    user.last_seen = datetime.now(timezone.utc)
    await session.commit()
    return True


async def is_authorised(session: AsyncSession, telegram_id: str) -> bool:
    user = await session.get(BotUser, telegram_id)
    return user is not None and user.install_id is not None


# ─── Command handlers ──────────────────────────────────────────────
WELCOME = (
    "👋 Привет! Это бот *Chimera*.\n\n"
    "Чтобы привязать ваш Chimera к этому чату, отправьте:\n"
    "`/verify КОД` — 6-значный код из приложения.\n\n"
    "Команды:\n"
    "• /verify КОД — привязать устройство\n"
    "• /devices — статус телефонов\n"
    "• /posts — черновики постов\n"
    "• /faq — частые вопросы\n"
    "• /help — справка"
)


async def verify_hw_code(client: httpx.AsyncClient, session: AsyncSession,
                         chat_id: int, user_id: str, username: str,
                         code: str) -> None:
    """Verify a hardware-binding code via /api/v1/auth/verify-from-bot."""
    try:
        r = await client.post(
            f"{APP_API_BASE}/api/v1/auth/verify-from-bot",
            json={
                "code": code,
                "telegram_id": int(user_id),
                "telegram_username": username,
            },
            headers={"X-Bot-Secret": os.environ["CHIMERA_BOT_SECRET"]},
            timeout=10.0,
        )
        data = r.json()
    except Exception as exc:
        log.warning("verify-from-bot failed: %s", exc)
        await send_text(client, chat_id, "❌ Sidecar недоступен. Проверьте, что приложение запущено.")
        return

    if data.get("ok"):
        user = await session.get(BotUser, user_id)
        if user is None:
            user = BotUser(telegram_id=user_id, install_id=data.get("hardware_id", "hw"), auth_code=code)
            session.add(user)
        else:
            user.install_id = data.get("hardware_id", user.install_id)
            user.auth_code = code
        user.last_seen = datetime.now(timezone.utc)
        await session.commit()
        await send_text(
            client, chat_id,
            f"✅ {data.get('message', 'Устройство авторизовано!')}",
        )
    else:
        await send_text(client, chat_id, f"❌ {data.get('error', 'Ошибка верификации')}")


async def handle_command(client: httpx.AsyncClient, session: AsyncSession,
                         msg: dict) -> None:
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    user_id = str(msg["from"]["id"])
    username = msg.get("from", {}).get("username", "")

    if text.startswith("/verify"):
        parts = text.split(maxsplit=1)
        code = parts[1].strip() if len(parts) > 1 else None
        if code:
            await verify_hw_code(client, session, chat_id, user_id, username, code)
        else:
            await send_text(client, chat_id, "Использование: `/verify КОД` (6-значный код из приложения)")
        return

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        code = parts[1].strip() if len(parts) > 1 else None
        if code:
            if code.isdigit() and len(code) == 6:
                await verify_hw_code(client, session, chat_id, user_id, username, code)
                return
            ok = await auth_user(session, user_id, code)
            if ok:
                await send_text(client, chat_id, "✅ Доступ подтверждён. Приятной работы!")
            else:
                await send_text(
                    client, chat_id,
                    "❌ Не удалось подтвердить код. Сгенерируйте новый в приложении.")
        else:
            await send_text(client, chat_id, WELCOME)
        return

    if not await is_authorised(session, user_id):
        await send_text(
            client, chat_id,
            "🔒 Сначала подтвердите доступ: `/start КОД` (код в приложении).")
        return

    if text.startswith("/devices") or text == "📱 Устройства":
        devices = await fetch_devices(client)
        if not devices:
            await send_text(client, chat_id, "_Устройств не найдено._")
            return
        lines = ["📱 *Устройства*\n"]
        for d in devices[:30]:
            dot = {"online": "🟢", "warming": "🟡", "offline": "🔴"}.get(d.get("status"), "⚪")
            ip = d.get("ip_address") or "—"
            lines.append(
                f"{dot} *{d.get('name')}* · {d.get('platform')} · IP `{ip}`"
            )
        await send_text(client, chat_id, "\n".join(lines))
        return

    if text.startswith("/posts") or text == "📝 Посты":
        posts = await fetch_pending_posts(client)
        if not posts:
            await send_text(client, chat_id, "_Черновиков нет._")
            return
        lines = ["📝 *Черновики постов* (выберите номер для подробностей)\n"]
        for i, p in enumerate(posts[:10], 1):
            cap = (p.get("caption") or "").replace("\n", " ")
            cap = cap[:80] + ("…" if len(cap) > 80 else "")
            lines.append(f"{i}. _{p.get('platform')}_ · {cap}")
        await send_text(client, chat_id, "\n".join(lines))
        return

    if text.startswith("/faq") or text == "❓ FAQ":
        await send_text(client, chat_id, faq_text())
        return

    if text.startswith("/help"):
        await send_text(client, chat_id, WELCOME)
        return

    await send_text(client, chat_id, "Не понял. Попробуйте /help.")


# ─── Polling loop ──────────────────────────────────────────────────
async def run_bot() -> None:
    if not BOT_TOKEN or BOT_TOKEN.startswith("PASTE_"):
        log.error("BOT_TOKEN is not configured. Edit chimera_bot.py or set CHIMERA_BOT_TOKEN.")
        return

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    offset = 0
    log.info("chimera-bot polling started")
    async with httpx.AsyncClient() as client:
        # Drop pending updates to avoid conflict with stale sessions
        try:
            await client.get(
                f"{API_BASE}/bot{BOT_TOKEN}/getUpdates",
                params={"offset": -1, "timeout": 0},
                timeout=10.0,
            )
            log.info("Dropped pending updates")
        except Exception:
            pass

        while True:
            try:
                r = await client.get(
                    f"{API_BASE}/bot{BOT_TOKEN}/getUpdates",
                    params={"timeout": 25, "offset": offset},
                    timeout=35.0,
                )
                r.raise_for_status()
                data = r.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 409:
                    log.warning("Bot conflict (409) — another instance may be running. Retrying in 10s...")
                    await asyncio.sleep(10)
                    continue
                log.warning("getUpdates failed: %s", exc)
                await asyncio.sleep(5)
                continue
            except Exception as exc:
                log.warning("getUpdates failed: %s", exc)
                await asyncio.sleep(5)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message")
                if not msg:
                    continue
                async with _Session() as session:
                    try:
                        await handle_command(client, session, msg)
                    except Exception as exc:
                        log.exception("handler error: %s", exc)


# ─── Outbound: forward in-app notifications to subscribers ─────────
async def broadcast_notification(text: str) -> None:
    """Called by the Chimera backend whenever a notification appears in-app."""
    if not BOT_TOKEN or BOT_TOKEN.startswith("PASTE_"):
        return
    async with _Session() as session:
        rows = (await session.execute(select(BotUser))).scalars().all()
        chat_ids = [u.telegram_id for u in rows if u.install_id]
    if not chat_ids:
        return
    async with httpx.AsyncClient() as client:
        for chat_id in chat_ids:
            await send_text(client, chat_id, text)


if __name__ == "__main__":
    asyncio.run(run_bot())
