"""
Сервис уведомлений: создание в БД, публикация в Redis для Telegram-бота.
Зависит от: database, redis_client, models/notification
"""

import structlog
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.notification import Notification
from app.services.redis_client import redis_client

logger = structlog.get_logger()


class NotificationService:

    async def create(
        self,
        user_id: UUID,
        type: str,
        title: str,
        message: str = "",
        data: Optional[Dict[str, Any]] = None,
        send_telegram: bool = True,
    ) -> Notification:
        """Создание уведомления в БД и отправка в Telegram"""
        async with async_session_factory() as db:
            notification = Notification(
                user_id=user_id,
                type=type,
                title=title,
                message=message,
                data=data or {},
            )
            db.add(notification)
            await db.commit()
            await db.refresh(notification)

        logger.info("notification.created", user_id=str(user_id), type=type, title=title)

        if send_telegram:
            await self._send_telegram(user_id, type, title, message, data)

        return notification

    async def _send_telegram(
        self, user_id: UUID, type: str, title: str, message: str, data: Optional[Dict]
    ):
        """Публикация в Redis для Telegram-бота"""
        emoji_map = {
            "device_online": "📱",
            "device_offline": "📱",
            "device_error": "⚠️",
            "post_success": "📝✅",
            "post_failed": "📝❌",
            "ban": "🚫",
            "login_success": "🔑✅",
            "login_failed": "🔑❌",
            "captcha_detected": "🔒",
            "captcha_solved": "🔓✅",
            "captcha_failed": "🔒❌",
            "calibration_done": "✅",
            "system_error": "⚠️",
        }
        emoji = emoji_map.get(type, "📌")

        await redis_client.publish("chimera:telegram_notifications", {
            "user_id": str(user_id),
            "type": type,
            "emoji": emoji,
            "title": title,
            "message": message,
            "data": data or {},
        })

    async def notify_device_status(self, user_id: UUID, device_name: str, status: str):
        """Уведомление о статусе устройства"""
        if status == "online":
            await self.create(user_id, "device_online", f"📱 {device_name} онлайн")
        elif status == "offline":
            await self.create(user_id, "device_offline", f"📱 {device_name} офлайн")
        elif status == "error":
            await self.create(user_id, "device_error", f"⚠️ {device_name} ошибка", send_telegram=True)

    async def notify_post_result(self, user_id: UUID, platform: str, username: str, success: bool, error: str = ""):
        """Уведомление о результате публикации"""
        if success:
            await self.create(user_id, "post_success", f"📝 Пост опубликован: {username} ({platform})")
        else:
            await self.create(user_id, "post_failed", f"📝 Ошибка публикации: {username}", message=error)

    async def notify_ban(self, user_id: UUID, platform: str, username: str, reason: str = ""):
        """Уведомление о бане/лимите"""
        await self.create(user_id, "ban", f"🚫 Бан: {username} ({platform})", message=reason)

    async def notify_login(self, user_id: UUID, platform: str, username: str, success: bool, error: str = ""):
        """Уведомление о входе в аккаунт"""
        t = "login_success" if success else "login_failed"
        title = f"🔑 Вход {'успешен' if success else 'не удался'}: {username} ({platform})"
        await self.create(user_id, t, title, message=error)

    async def notify_captcha(self, user_id: UUID, platform: str, status: str):
        """Уведомление о капче"""
        statuses = {
            "detected": ("captcha_detected", "🔒 Капча обнаружена"),
            "solving": ("captcha_detected", "🔒 Решаем капчу..."),
            "solved": ("captcha_solved", "🔓 Капча решена"),
            "failed": ("captcha_failed", "🔒 Капча не решена"),
        }
        t, title = statuses.get(status, ("captcha_detected", f"🔒 Капча: {status}"))
        await self.create(user_id, t, f"{title} ({platform})")

    async def notify_calibration(self, user_id: UUID, device_name: str, passed: bool):
        """Уведомление о калибровке"""
        if passed:
            await self.create(user_id, "calibration_done", f"✅ Калибровка завершена: {device_name}")
        else:
            await self.create(user_id, "device_error", f"⚠️ Калибровка не пройдена: {device_name}")


notification_service = NotificationService()
