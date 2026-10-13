r"""
Chimera Telegram Bot v9.0 — управление системой через Telegram.
Зависит от: python-telegram-bot v20+, httpx, matplotlib
Отдельный процесс, общается с FastAPI backend через HTTP API.

Запуск:
  cd "C:\chimera project"
  py bot/chimera_bot.py

Настройка:
  1. Получите токен у @BotFather
  2. Замените BOT_TOKEN ниже
  3. Запустите скрипт
"""

BOT_TOKEN = os.environ["CHIMERA_BOT_TOKEN"]
API_BASE_URL = "http://localhost:17842"

import asyncio
import atexit
import io
import logging
import os
import sys
from datetime import datetime, timedelta

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

import httpx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("chimera_bot")

API_TIMEOUT = 15.0


# ═══ HTTP-клиент к FastAPI ═══

async def api_get(path: str, token: str = "") -> dict:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=API_TIMEOUT) as client:
        resp = await client.get(path, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def api_post(path: str, data: dict = None, token: str = "") -> dict:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=API_TIMEOUT) as client:
        resp = await client.post(path, json=data or {}, headers=headers)
        resp.raise_for_status()
        return resp.json()


# ═══ Хранение состояния пользователей ═══

user_tokens: dict[int, str] = {}
verified_users: set[int] = set()


def get_token(telegram_id: int) -> str:
    return user_tokens.get(telegram_id, "")


def is_verified(telegram_id: int) -> bool:
    return telegram_id in verified_users


# ═══ Авторизация: синхронизация с десктоп-приложением ═══

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и авторизация"""
    args = context.args

    if args and len(args) == 1:
        code = args[0]
        telegram_id = update.effective_user.id
        try:
            result = await api_post("/api/auth/bot-confirm", {
                "code": code,
                "telegram_id": str(telegram_id),
            })
            if result.get("ok"):
                verified_users.add(telegram_id)
                user_tokens[telegram_id] = result.get("install_id", "")
                await update.message.reply_text(
                    "✅ *Авторизация успешна!*\n\n"
                    "Ваш Telegram привязан к Chimera.\n"
                    "Приложение на компьютере разблокировано автоматически.\n\n"
                    "Используйте /help для списка команд.",
                    parse_mode="Markdown"
                )
                return
            else:
                await update.message.reply_text(
                    "❌ Неверный или истёкший код.\n"
                    "Получите новый код в приложении Chimera."
                )
                return
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                await update.message.reply_text(
                    "❌ Неверный или истёкший код.\n"
                    "Получите новый код в приложении Chimera."
                )
            else:
                await update.message.reply_text(f"❌ Ошибка API: {e.response.status_code}")
            return
        except httpx.ConnectError:
            await update.message.reply_text(
                "❌ Chimera не запущена. Запустите приложение на компьютере."
            )
            return
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка авторизации: {e}")
            return

    text = (
        "👋 Добро пожаловать в *Chimera Bot* v9.0!\n\n"
        "Этот бот управляет вашей фермой устройств.\n\n"
        "📋 *Авторизация:*\n"
        "1. Откройте приложение Chimera на компьютере\n"
        "2. Нажмите *«Получить код»*\n"
        "3. Отправьте боту: `/verify КОД`\n"
        "   или используйте ссылку из приложения\n\n"
        "⚡ Один код — один компьютер — один аккаунт.\n"
        "Код подтверждается через этот бот.\n\n"
        "Используйте /help для списка команд."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Привязка Telegram-аккаунта к Chimera"""
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите код: `/verify XXXXXX`\n\n"
            "Получите код в приложении Chimera → кнопка «Получить код»",
            parse_mode="Markdown"
        )
        return

    code = context.args[0]
    telegram_id = update.effective_user.id

    try:
        result = await api_post("/api/auth/bot-confirm", {
            "code": code,
            "telegram_id": str(telegram_id),
        })

        if result.get("ok"):
            verified_users.add(telegram_id)
            user_tokens[telegram_id] = result.get("install_id", "")
            await update.message.reply_text(
                "✅ *Верификация успешна!*\n\n"
                "Ваш Telegram привязан к Chimera.\n"
                "Приложение на компьютере разблокировано автоматически.\n\n"
                "Теперь вы можете:\n"
                "• Управлять устройствами: /devices\n"
                "• Смотреть статус: /status\n"
                "• Создавать посты: /post\n"
                "• Получать уведомления автоматически\n\n"
                "Используйте /help для полного списка команд.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "❌ Неверный код верификации.\n\n"
                "Убедитесь, что:\n"
                "• Код скопирован правильно\n"
                "• Приложение Chimera запущено\n"
                "• Код не использовался ранее\n\n"
                "Получите новый код в приложении."
            )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            await update.message.reply_text(
                "❌ Неверный или истёкший код.\n\n"
                "Убедитесь, что:\n"
                "• Код скопирован правильно\n"
                "• Приложение Chimera запущено\n"
                "• Код не использовался ранее\n\n"
                "Получите новый код в приложении."
            )
        else:
            await update.message.reply_text(f"❌ Ошибка API: {e.response.status_code}")
    except httpx.ConnectError:
        await update.message.reply_text(
            "❌ Chimera не запущена на компьютере.\n\n"
            "Запустите приложение и попробуйте снова."
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статус системы"""
    if not is_verified(update.effective_user.id):
        await update.message.reply_text("🔒 Сначала выполните /verify КОД")
        return

    try:
        health = await api_get("/health")
        devices = await api_get("/api/devices")
        tasks = await api_get("/api/tasks/stats")

        device_list = devices if isinstance(devices, list) else devices.get("items", [])
        online = sum(1 for d in device_list if d.get("status") == "online")
        offline = sum(1 for d in device_list if d.get("status") == "offline")
        error = sum(1 for d in device_list if d.get("status") == "error")

        text = (
            "📊 *Статус системы Chimera v9.0*\n\n"
            f"🖥 Сервер: {health.get('status', 'unknown')}\n"
            f"🗄 База данных: {health.get('database', 'unknown')}\n"
            f"📱 Версия: {health.get('version', '?')}\n\n"
            f"*Устройства ({len(device_list)}):*\n"
            f"  🟢 Онлайн: {online}\n"
            f"  🔴 Офлайн: {offline}\n"
            f"  ⚠️ Ошибки: {error}\n\n"
        )

        if isinstance(tasks, dict):
            text += (
                f"*Задачи:*\n"
                f"  ⏳ Ожидают: {tasks.get('pending', 0)}\n"
                f"  ▶️ Выполняются: {tasks.get('running', 0)}\n"
                f"  ✅ Завершены: {tasks.get('completed', 0)}\n"
                f"  ❌ Ошибки: {tasks.get('failed', 0)}\n"
            )

        await update.message.reply_text(text, parse_mode="Markdown")
    except httpx.ConnectError:
        await update.message.reply_text("❌ Chimera не запущена на компьютере.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def cmd_devices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список устройств"""
    if not is_verified(update.effective_user.id):
        await update.message.reply_text("🔒 Сначала выполните /verify КОД")
        return

    try:
        devices = await api_get("/api/devices")
        device_list = devices if isinstance(devices, list) else devices.get("items", [])

        if not device_list:
            await update.message.reply_text(
                "📱 Нет подключённых устройств.\n\n"
                "Подключите Android-телефон по USB — агент установится автоматически."
            )
            return

        status_emoji = {
            "online": "🟢", "offline": "🔴", "busy": "🟡",
            "error": "⚠️", "paused": "⏸", "calibrating": "🔧"
        }

        text = "📱 *Устройства*\n\n"
        keyboard = []
        for d in device_list[:20]:
            emoji = status_emoji.get(d.get("status", ""), "❓")
            battery = d.get("battery_level")
            battery_str = f" 🔋{battery}%" if battery is not None else ""
            text += (
                f"{emoji} *{d.get('name', '?')}*\n"
                f"  {d.get('platform', '?')} · {d.get('ip_address', 'нет IP')}"
                f"{battery_str}\n\n"
            )
            if d.get("status") == "online":
                keyboard.append([
                    InlineKeyboardButton(
                        f"📸 {d.get('name', d.get('id', '?')[:8])}",
                        callback_data=f"screenshot:{d.get('id', '')}"
                    ),
                    InlineKeyboardButton(
                        f"📲 Установить агент",
                        callback_data=f"install_agent:{d.get('id', '')}"
                    ),
                ])

        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def cmd_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список аккаунтов"""
    if not is_verified(update.effective_user.id):
        await update.message.reply_text("🔒 Сначала выполните /verify КОД")
        return

    try:
        accounts = await api_get("/api/accounts")
        account_list = accounts if isinstance(accounts, list) else accounts.get("items", [])

        if not account_list:
            await update.message.reply_text("👤 Нет аккаунтов. Добавьте в приложении Chimera.")
            return

        platform_emoji = {
            "instagram": "📸", "telegram": "✈️", "tiktok": "🎵",
            "facebook": "📘", "twitter": "🐦", "linkedin": "💼",
            "youtube": "📺", "reddit": "🤖", "threads": "🧵", "vk": "🔵"
        }

        status_emoji = {
            "active": "🟢", "warming": "🟡", "paused": "⏸",
            "banned": "🚫", "suspended": "⛔", "limited": "⚠️"
        }

        text = "👤 *Аккаунты*\n\n"
        for a in account_list[:20]:
            pe = platform_emoji.get(a.get("platform", ""), "📱")
            se = status_emoji.get(a.get("status", ""), "❓")
            text += (
                f"{pe} *{a.get('username', '?')}* ({a.get('platform', '?')})\n"
                f"  {se} {a.get('status', '?')}\n\n"
            )

        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск автоматической регистрации аккаунта"""
    if not is_verified(update.effective_user.id):
        await update.message.reply_text("🔒 Сначала выполните /verify КОД")
        return

    try:
        devices = await api_get("/api/devices")
        device_list = devices if isinstance(devices, list) else devices.get("items", [])
        online = [d for d in device_list if d.get("status") == "online"]

        if not online:
            await update.message.reply_text("📱 Нет онлайн-устройств для регистрации.")
            return

        platforms = ["instagram", "tiktok", "facebook", "twitter", "linkedin", "vk", "reddit"]
        keyboard = [
            [InlineKeyboardButton(
                f"📱 {p.capitalize()}",
                callback_data=f"reg_platform:{p}"
            )]
            for p in platforms
        ]
        await update.message.reply_text(
            "📝 *Регистрация нового аккаунта*\n\n"
            "Выберите платформу:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def cmd_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скриншот устройства"""
    if not is_verified(update.effective_user.id):
        await update.message.reply_text("🔒 Сначала выполните /verify КОД")
        return

    if not context.args:
        try:
            devices = await api_get("/api/devices")
            device_list = devices if isinstance(devices, list) else devices.get("items", [])
            online = [d for d in device_list if d.get("status") == "online"]

            if not online:
                await update.message.reply_text("📱 Нет онлайн-устройств")
                return

            keyboard = [
                [InlineKeyboardButton(
                    f"📱 {d.get('name', d.get('id', '?')[:8])}",
                    callback_data=f"screenshot:{d.get('id', '')}"
                )]
                for d in online[:10]
            ]
            await update.message.reply_text(
                "📸 Выберите устройство:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
        return

    device_id = context.args[0]
    await _take_screenshot(update, device_id)


async def _take_screenshot(update_or_query, device_id: str):
    try:
        msg = getattr(update_or_query, 'message', None) or update_or_query.callback_query.message
        status_msg = await msg.reply_text("📸 Делаю скриншот...")

        result = await api_post(f"/api/streaming/{device_id}/screenshot")

        if result.get("screenshot"):
            import base64
            img_data = base64.b64decode(result["screenshot"])
            await msg.reply_photo(
                photo=io.BytesIO(img_data),
                caption=f"📱 Скриншот устройства"
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Не удалось получить скриншот")
    except Exception as e:
        try:
            msg = getattr(update_or_query, 'message', None) or update_or_query.callback_query.message
            await msg.reply_text(f"❌ Ошибка: {e}")
        except Exception:
            pass


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика с графиком"""
    if not is_verified(update.effective_user.id):
        await update.message.reply_text("🔒 Сначала выполните /verify КОД")
        return

    try:
        period = 7
        if context.args:
            try:
                period = int(context.args[0])
                period = max(1, min(90, period))
            except ValueError:
                pass

        analytics = await api_get(f"/api/dashboard/stats?days={period}")
        data = analytics if isinstance(analytics, list) else analytics.get("data", [])

        if not data:
            devices = await api_get("/api/devices")
            accounts = await api_get("/api/accounts")
            device_list = devices if isinstance(devices, list) else devices.get("items", [])
            account_list = accounts if isinstance(accounts, list) else accounts.get("items", [])

            text = (
                f"📊 *Статистика за {period} дней*\n\n"
                f"📱 Устройств: {len(device_list)}\n"
                f"👤 Аккаунтов: {len(account_list)}\n"
                f"📝 Постов за период: 0\n\n"
                f"Нет данных для построения графика."
            )
            await update.message.reply_text(text, parse_mode="Markdown")
            return

        dates = [datetime.fromisoformat(d.get("date", "2025-01-01")) for d in data]
        published = [d.get("published", 0) for d in data]
        failed = [d.get("failed", 0) for d in data]

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(dates, published, color="#4CAF50", alpha=0.8, label="Опубликовано")
        ax.bar(dates, failed, bottom=published, color="#F44336", alpha=0.8, label="Ошибки")
        ax.set_title(f"Публикации за {period} дней", fontsize=14)
        ax.set_xlabel("Дата")
        ax.set_ylabel("Количество")
        ax.legend()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
        plt.xticks(rotation=45)
        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120)
        plt.close(fig)
        buf.seek(0)

        total_pub = sum(published)
        total_fail = sum(failed)
        caption = (
            f"📊 *Статистика за {period} дней*\n\n"
            f"✅ Опубликовано: {total_pub}\n"
            f"❌ Ошибки: {total_fail}\n"
            f"📈 Всего: {total_pub + total_fail}"
        )

        await update.message.reply_photo(
            photo=buf,
            caption=caption,
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def cmd_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Интерактивная публикация поста"""
    if not is_verified(update.effective_user.id):
        await update.message.reply_text("🔒 Сначала выполните /verify КОД")
        return

    try:
        accounts = await api_get("/api/accounts")
        account_list = accounts if isinstance(accounts, list) else accounts.get("items", [])
        active = [a for a in account_list if a.get("status") in ("active", "warming")]

        if not active:
            await update.message.reply_text("👤 Нет активных аккаунтов для публикации")
            return

        keyboard = [
            [InlineKeyboardButton(
                f"📱 {a.get('username', '?')} ({a.get('platform', '?')})",
                callback_data=f"post_account:{a.get('id', '')}"
            )]
            for a in active[:10]
        ]
        await update.message.reply_text(
            "📝 *Публикация поста*\n\nВыберите аккаунт:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр и управление планами"""
    if not is_verified(update.effective_user.id):
        await update.message.reply_text("🔒 Сначала выполните /verify КОД")
        return

    try:
        plans = await api_get("/api/settings")
        plan_list = plans if isinstance(plans, list) else plans.get("items", [])

        text = "📅 *Планы и расписание*\n\n"
        text += "Управление планами доступно в приложении Chimera:\n"
        text += "• Вкладка «Планировщик» → Добавить план\n"
        text += "• Выберите датасет, даты, аккаунты\n"
        text += "• Планы выполняются автоматически\n"

        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Последние записи лога"""
    if not is_verified(update.effective_user.id):
        await update.message.reply_text("🔒 Сначала выполните /verify КОД")
        return

    try:
        logs = await api_get("/api/tools/logs?limit=20")
        log_list = logs if isinstance(logs, list) else logs.get("items", [])

        if not log_list:
            await update.message.reply_text("📋 Нет записей")
            return

        text = "📋 *Последние логи*\n\n"
        for log in log_list[:20]:
            success = "✅" if log.get("success") else "❌"
            ts = log.get("created_at", "")[:16].replace("T", " ")
            text += f"`{ts}` {success} {log.get('action_type', '?')}\n"

        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список команд"""
    text = (
        "📖 *Команды Chimera Bot v9.0*\n\n"
        "*Авторизация:*\n"
        "/start — Приветствие\n"
        "/verify `код` — Привязка Telegram\n\n"
        "*Мониторинг:*\n"
        "/status — Статус системы\n"
        "/devices — Список устройств\n"
        "/accounts — Аккаунты\n"
        "/screenshot — Скриншот устройства\n"
        "/stats `дни` — Статистика (по умолчанию 7)\n"
        "/logs — Последние логи\n\n"
        "*Управление:*\n"
        "/post — Создать публикацию\n"
        "/register — Авто-регистрация аккаунта\n"
        "/schedule — Планы публикаций\n\n"
        "*Справка:*\n"
        "/faq — Частые вопросы\n"
        "/help — Эта справка\n\n"
        "💡 Уведомления приходят автоматически:\n"
        "устройство вкл/выкл, публикация ок/ошибка, бан, капча"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ═══ FAQ ═══

FAQ_CATEGORIES = {
    "devices": "📱 Устройства",
    "accounts": "👤 Аккаунты",
    "posting": "📝 Публикации",
    "security": "🔒 Безопасность",
    "system": "⚙️ Система",
    "registration": "📋 Регистрация",
}

FAQ_DATA = {
    "android_connect": {
        "cat": "devices",
        "q": "Как подключить Android?",
        "a": (
            "📱 *Подключение Android-телефона:*\n\n"
            "1. *Настройки → О телефоне → Номер сборки* (7 нажатий)\n"
            "2. *Настройки → Для разработчиков:*\n"
            "   • ✅ Отладка по USB\n"
            "   • ✅ Не выключать экран\n"
            "3. Подключите к Wi-Fi (та же сеть)\n"
            "4. Подключите по USB — агент установится *автоматически*\n"
            "5. В приложении: устройство появится в списке"
        )
    },
    "ios_connect": {
        "cat": "devices",
        "q": "Как подключить iPhone?",
        "a": (
            "📱 *Подключение iPhone (Jailbreak):*\n\n"
            "*1. Определите инструмент:*\n"
            "  • A7-A11 (5s–X): checkra1n\n"
            "  • A12-A15, iOS 14.x: unc0ver\n"
            "  • A12+, iOS 15-16.6.1: Dopamine\n\n"
            "*2. Выполните джейлбрейк*\n\n"
            "*3. Установите через Cydia/Sileo:*\n"
            "  • OpenSSH\n"
            "  • WebDriverAgent\n"
            "  • Liberty Lite (скрытие JB)\n\n"
            "*4. На Mac:*\n"
            "  `brew install node`\n"
            "  `npm i -g appium`\n"
            "  `appium driver install xcuitest`"
        )
    },
    "proxy_setup": {
        "cat": "security",
        "q": "Как настроить прокси?",
        "a": (
            "🔒 *Настройка прокси:*\n\n"
            "*Типы:* HTTP/HTTPS, SOCKS5, Residential\n\n"
            "*Где купить:*\n"
            "  Bright Data, Smartproxy, 922proxy\n\n"
            "*Настройка:*\n"
            "  Настройки → Прокси → Добавить\n\n"
            "*Проверка автоматическая:*\n"
            "  ✅ Работоспособность\n"
            "  ✅ DNS-утечки\n"
            "  ✅ WebRTC-утечки"
        )
    },
    "ban_reasons": {
        "cat": "accounts",
        "q": "Почему аккаунт забанили?",
        "a": (
            "🚫 *Причины бана:*\n\n"
            "• Быстрые действия\n"
            "• Много подписок/отписок\n"
            "• Повторяющийся контент\n"
            "• Подозрительный IP\n\n"
            "*Профилактика:*\n"
            "• Прогрев 3-7 дней\n"
            "• Residential прокси\n"
            "• Не более 3 акк/телефон\n\n"
            "*Если забанили:*\n"
            "• Остановите автоматизацию\n"
            "• Смените прокси\n"
            "• Подождите 24-48ч"
        )
    },
    "autoposting": {
        "cat": "posting",
        "q": "Как настроить автопостинг?",
        "a": (
            "📝 *Автопостинг:*\n\n"
            "1. Загрузите фото: Датасеты → Загрузить\n"
            "2. Планировщик → Добавить план\n"
            "   • Выберите датасет\n"
            "   • Даты, частота\n"
            "   • Выберите аккаунты\n"
            "3. План выполняется автоматически\n\n"
            "*SIPR-микширование:*\n"
            "  Равномерный расход фотографий"
        )
    },
    "warmup_info": {
        "cat": "accounts",
        "q": "Как работает прогрев?",
        "a": (
            "🔥 *Прогрев аккаунтов:*\n\n"
            "Лайки, подписки, комментарии,\n"
            "скроллинг — всё с *человеческим курсором*\n\n"
            "*Адаптивный коэффициент:*\n"
            "  `min(1, устройств / 50)`\n\n"
            "Рекомендуется: 3-7 дней,\n"
            "интенсивность 3-5 из 10"
        )
    },
    "captcha_setup": {
        "cat": "security",
        "q": "Как настроить 2Captcha?",
        "a": (
            "🔒 *2Captcha:*\n\n"
            "1. Регистрация на 2captcha.com\n"
            "2. Пополните баланс (~$3)\n"
            "3. Скопируйте API-ключ\n"
            "4. Настройки → 2Captcha → Вставить\n\n"
            "*Поддержка:*\n"
            "  reCAPTCHA v2/v3, hCaptcha, image\n\n"
            "*Fallback:* уведомление в Telegram"
        )
    },
    "phone_not_connecting": {
        "cat": "devices",
        "q": "Телефон не подключается?",
        "a": (
            "🔧 *Чеклист:*\n\n"
            "✅ Одна Wi-Fi сеть\n"
            "✅ Режим разработчика\n"
            "✅ USB-отладка\n"
            "✅ Agent установлен\n"
            "✅ Файрвол не блокирует\n\n"
            "*iOS дополнительно:*\n"
            "✅ Jailbreak выполнен\n"
            "✅ Appium запущен\n"
            "✅ WebDriverAgent установлен"
        )
    },
    "update_app": {
        "cat": "system",
        "q": "Как обновить?",
        "a": (
            "⚙️ *Обновление:*\n\n"
            "1. `git pull`\n"
            "2. `npm install`\n"
            "3. `pip install -r requirements.txt`\n"
            "4. Перезапустите приложение\n\n"
            "БД мигрирует автоматически."
        )
    },
    "auto_register": {
        "cat": "registration",
        "q": "Как авто-регистрировать аккаунт?",
        "a": (
            "📋 *Авто-регистрация:*\n\n"
            "1. Аккаунты → «Создать новый аккаунт»\n"
            "2. Введите email и пароль от email\n"
            "3. Выберите платформу и телефон\n"
            "4. Нажмите «Начать регистрацию»\n\n"
            "*Процесс:*\n"
            "  • Открытие приложения на телефоне\n"
            "  • Ввод данных (человеческий курсор)\n"
            "  • Email-верификация (IMAP)\n"
            "  • Решение капчи (2Captcha)\n\n"
            "Или через бот: /register"
        )
    },
    "human_cursor": {
        "cat": "security",
        "q": "Как работает человеческий курсор?",
        "a": (
            "👆 *Human Cursor:*\n\n"
            "Имитация реального пальца:\n"
            "  • Кривые Безье (3-4 точки)\n"
            "  • Overshoot ±2-7px\n"
            "  • Микротремор 8-12Hz\n"
            "  • Ease-in-out скорость\n"
            "  • Опечатки при вводе (1/15)\n"
            "  • Пауссоновские задержки\n\n"
            "Неотличим от реального пользователя."
        )
    },
    "antidetect_info": {
        "cat": "security",
        "q": "Как работает антидетект?",
        "a": (
            "🛡 *Антидетект:*\n\n"
            "*Fingerprint:* ротация/24ч\n"
            "  device_id, IMEI, serial, MAC\n\n"
            "*Метаданные фото:*\n"
            "  EXIF очистка + подмена + LSB\n\n"
            "*Поведение:*\n"
            "  Пуассоновские задержки,\n"
            "  человеческий курсор,\n"
            "  уникальные паттерны"
        )
    },
    "screen_streaming": {
        "cat": "system",
        "q": "Демонстрация экрана?",
        "a": (
            "📺 *Стриминг:*\n\n"
            "Android → H.264 HW → WebSocket\n"
            "→ WebCodecs API → Canvas\n\n"
            "iOS → скриншоты 5 FPS → MJPEG\n\n"
            "Задержка: <100ms (LAN)\n"
            "FPS: до 30 (Android)\n\n"
            "Настройки: качество, FPS, оверлей"
        )
    },
    "export_data": {
        "cat": "system",
        "q": "Как экспортировать данные?",
        "a": (
            "📊 *Экспорт:*\n\n"
            "• Логи → CSV: кнопка «Экспорт»\n"
            "• Аналитика → Excel: «Скачать отчёт»\n"
            "• Бэкап БД: скопируйте chimera.db"
        )
    },
    "scheduler_setup": {
        "cat": "posting",
        "q": "Как настроить планировщик?",
        "a": (
            "📅 *Планировщик:*\n\n"
            "1. Добавить план\n"
            "2. Выберите датасет, даты\n"
            "3. Постов в день: 1-5\n"
            "4. *Выберите конкретные аккаунты*\n"
            "5. Стиль подписи\n"
            "6. Сохранить\n\n"
            "Планы выполняются через APScheduler."
        )
    },
    "reassign_account": {
        "cat": "accounts",
        "q": "Привязка к другому телефону?",
        "a": (
            "🔄 *Перепривязка:*\n\n"
            "Аккаунты → карта → drag & drop\n"
            "аккаунт на другой телефон.\n\n"
            "Линия перерисуется в цвет платформы."
        )
    },
    "accounts_per_phone": {
        "cat": "accounts",
        "q": "Сколько аккаунтов на телефон?",
        "a": "📱 Рекомендация: 1-3 аккаунта.\nС разными прокси для каждого."
    },
}


async def cmd_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """FAQ с категориями"""
    keyboard = [
        [InlineKeyboardButton(cat_name, callback_data=f"faq_cat:{cat_id}")]
        for cat_id, cat_name in FAQ_CATEGORIES.items()
    ]
    await update.message.reply_text(
        "❓ *FAQ — Частые вопросы*\n\nВыберите категорию:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# ═══ Callback handlers ═══

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка inline-кнопок"""
    query = update.callback_query
    await query.answer()

    data = query.data or ""

    if data.startswith("faq_cat:"):
        cat_id = data.split(":")[1]
        items = [
            (faq_id, faq)
            for faq_id, faq in FAQ_DATA.items()
            if faq["cat"] == cat_id
        ]
        keyboard = [
            [InlineKeyboardButton(faq["q"], callback_data=f"faq:{faq_id}")]
            for faq_id, faq in items
        ]
        keyboard.append([InlineKeyboardButton("← Назад", callback_data="faq_back")])
        cat_name = FAQ_CATEGORIES.get(cat_id, "FAQ")
        await query.edit_message_text(
            f"❓ *{cat_name}*\n\nВыберите вопрос:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("faq:"):
        faq_id = data.split(":")[1]
        faq = FAQ_DATA.get(faq_id)
        if faq:
            answer = faq["a"] if isinstance(faq["a"], str) else str(faq["a"])
            keyboard = [[InlineKeyboardButton("← Назад к категориям", callback_data="faq_back")]]
            await query.edit_message_text(
                answer,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

    elif data == "faq_back":
        keyboard = [
            [InlineKeyboardButton(cat_name, callback_data=f"faq_cat:{cat_id}")]
            for cat_id, cat_name in FAQ_CATEGORIES.items()
        ]
        await query.edit_message_text(
            "❓ *FAQ — Частые вопросы*\n\nВыберите категорию:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("screenshot:"):
        device_id = data.split(":")[1]
        if is_verified(update.effective_user.id):
            await _take_screenshot(update, device_id)

    elif data.startswith("install_agent:"):
        device_id = data.split(":")[1]
        if is_verified(update.effective_user.id):
            try:
                result = await api_post(
                    f"/api/registration/devices/{device_id}/install-agent"
                )
                if result.get("ok"):
                    await query.edit_message_text(f"📲 {result.get('message', 'Установка запущена')}")
                else:
                    await query.edit_message_text(f"❌ {result.get('error', 'Ошибка')}")
            except Exception as e:
                await query.edit_message_text(f"❌ Ошибка: {e}")

    elif data.startswith("reg_platform:"):
        platform = data.split(":")[1]
        context.user_data["reg_platform"] = platform
        await query.edit_message_text(
            f"📝 Платформа: *{platform.capitalize()}*\n\n"
            f"Отправьте email для регистрации:",
            parse_mode="Markdown"
        )

    elif data.startswith("reg_device:"):
        device_id = data.split(":")[1]
        if not is_verified(update.effective_user.id):
            return
        platform = context.user_data.get("reg_platform", "")
        email = context.user_data.get("reg_email", "")
        email_pass = context.user_data.get("reg_email_pass", "")

        try:
            result = await api_post("/api/registration/register-new", {
                "email": email,
                "email_password": email_pass,
                "platform": platform,
                "device_id": device_id,
            })
            if result.get("ok"):
                await query.edit_message_text(
                    f"✅ Регистрация запущена!\n\n"
                    f"Платформа: {platform}\n"
                    f"Email: {email}\n\n"
                    f"Прогресс можно отслеживать в приложении Chimera."
                )
            else:
                await query.edit_message_text(f"❌ {result.get('error', 'Ошибка')}")
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка: {e}")

        for key in ("reg_platform", "reg_email", "reg_email_pass"):
            context.user_data.pop(key, None)

    elif data.startswith("post_account:"):
        account_id = data.split(":")[1]
        context.user_data["post_account_id"] = account_id
        await query.edit_message_text(
            "📝 Отправьте текст подписи к посту\n"
            "(или напишите `auto` для автогенерации):",
            parse_mode="Markdown"
        )

    elif data.startswith("confirm_post:"):
        if is_verified(update.effective_user.id):
            account_id = context.user_data.get("post_account_id", "")
            caption = context.user_data.get("post_caption", "")
            try:
                result = await api_post("/api/posts", {
                    "account_id": account_id,
                    "caption": caption,
                    "status": "scheduled",
                })
                await query.edit_message_text("✅ Пост создан и поставлен в очередь!")
            except Exception as e:
                await query.edit_message_text(f"❌ Ошибка: {e}")
        context.user_data.pop("post_account_id", None)
        context.user_data.pop("post_caption", None)

    elif data == "cancel_post":
        context.user_data.pop("post_account_id", None)
        context.user_data.pop("post_caption", None)
        await query.edit_message_text("❌ Публикация отменена")


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    text = update.message.text or ""

    # Registration flow: email input
    if "reg_platform" in context.user_data and "reg_email" not in context.user_data:
        if "@" in text:
            context.user_data["reg_email"] = text.strip()
            await update.message.reply_text(
                f"📧 Email: *{text.strip()}*\n\n"
                f"Теперь отправьте пароль от этого email:",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Введите корректный email (с @)")
        return

    # Registration flow: password input
    if "reg_email" in context.user_data and "reg_email_pass" not in context.user_data:
        context.user_data["reg_email_pass"] = text.strip()
        if not is_verified(update.effective_user.id):
            await update.message.reply_text("🔒 Сначала /verify КОД")
            return

        try:
            devices = await api_get("/api/devices")
            device_list = devices if isinstance(devices, list) else devices.get("items", [])
            online = [d for d in device_list if d.get("status") == "online"]

            if not online:
                await update.message.reply_text("📱 Нет онлайн-устройств.")
                return

            keyboard = [
                [InlineKeyboardButton(
                    f"📱 {d.get('name', '?')}",
                    callback_data=f"reg_device:{d.get('id', '')}"
                )]
                for d in online[:10]
            ]
            platform = context.user_data.get("reg_platform", "?")
            email = context.user_data.get("reg_email", "?")
            await update.message.reply_text(
                f"📋 *Регистрация {platform.capitalize()}*\n\n"
                f"Email: {email}\n"
                f"Пароль: {'•' * min(len(text), 8)}\n\n"
                f"Выберите устройство:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
        return

    # Post flow: caption input
    if "post_account_id" in context.user_data:
        caption = text
        context.user_data["post_caption"] = caption

        keyboard = [
            [
                InlineKeyboardButton("✅ Опубликовать", callback_data="confirm_post:yes"),
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_post"),
            ]
        ]

        preview = caption[:200] + ("..." if len(caption) > 200 else "")
        await update.message.reply_text(
            f"📝 *Подтверждение*\n\n"
            f"Подпись:\n{preview}\n\n"
            f"Опубликовать?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        "Используйте /help для списка команд."
    )


# ═══ Установка команд в меню Telegram ═══

async def post_init(application: Application) -> None:
    """Set bot commands visible in Telegram menu."""
    commands = [
        BotCommand("start", "Приветствие и авторизация"),
        BotCommand("verify", "Привязка Telegram (код)"),
        BotCommand("status", "Статус системы"),
        BotCommand("devices", "Список устройств"),
        BotCommand("accounts", "Аккаунты"),
        BotCommand("screenshot", "Скриншот устройства"),
        BotCommand("stats", "Статистика"),
        BotCommand("post", "Создать публикацию"),
        BotCommand("register", "Авто-регистрация аккаунта"),
        BotCommand("schedule", "Планы публикаций"),
        BotCommand("logs", "Последние логи"),
        BotCommand("faq", "Частые вопросы"),
        BotCommand("help", "Справка"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands registered")


# ═══ Запуск ═══

def main():
    if not BOT_TOKEN or BOT_TOKEN.startswith("ВСТАВЬТЕ"):
        print("=" * 50)
        print("  CHIMERA TELEGRAM BOT v9.0")
        print("=" * 50)
        print()
        print("  Настройка:")
        print("  1. Получите токен у @BotFather в Telegram")
        print("  2. Откройте bot/chimera_bot.py")
        print("  3. Замените BOT_TOKEN на ваш токен")
        print("  4. Запустите: py bot/chimera_bot.py")
        print()
        print(f"  API сервер: {API_BASE_URL}")
        print(f"  Бот файл: {os.path.abspath(__file__)}")
        return

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("verify", cmd_verify))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("devices", cmd_devices))
    app.add_handler(CommandHandler("accounts", cmd_accounts))
    app.add_handler(CommandHandler("screenshot", cmd_screenshot))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("post", cmd_post))
    app.add_handler(CommandHandler("register", cmd_register))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("logs", cmd_logs))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("faq", cmd_faq))

    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    async def error_handler(update, context):
        import telegram.error
        if isinstance(context.error, telegram.error.Conflict):
            logger.warning("Bot conflict detected — another instance may be running")
            return
        logger.error(f"Bot error: {context.error}")

    app.add_error_handler(error_handler)

    print("=" * 50)
    print("  CHIMERA TELEGRAM BOT v9.0")
    print("=" * 50)
    print(f"  API: {API_BASE_URL}")
    print(f"  Bot: @... (running)")
    print("  Ctrl+C to stop")
    print()

    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
