"""
Автоответ на комментарии: трекинг, определение пола, генерация ответа.
Зависит от: database, redis_client, models/comment, gender_guesser
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

import structlog
import gender_guesser.detector as gender_detector
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.comment import TrackedComment
from app.services.redis_client import redis_client

logger = structlog.get_logger()

# Инициализация определителя пола
_gender_detector = gender_detector.Detector()

# Шаблоны ответов
RESPONSE_TEMPLATES = {
    "intriguing": {
        "male": [
            "Интересная точка зрения 🤔 напиши мне в директ",
            "Хм, а расскажи подробнее... 😏",
            "Ты затронул важную тему, обсудим? 💬",
            "Спасибо за комментарий! Чувствую что мы на одной волне ✨",
            "Оо, интригующе! Продолжай 😉",
        ],
        "female": [
            "Какой интересный взгляд! 🤔 Давай обсудим в директ",
            "Ты на верном пути 😏 напиши мне",
            "Любопытно... расскажи больше 💫",
            "Класс! Мы точно найдём общий язык ✨",
        ],
    },
    "vulgar": {
        "male": [
            "Ой, а ты дерзкий 😈 загляни в директ",
            "Ммм, люблю таких смелых 💋 напиши мне",
            "Горячий комментарий 🔥 продолжим в личке?",
            "Ты точно знаешь что хочешь 😏 давай в директ",
        ],
        "female": [
            "Ого, какая ты смелая! 😈 Напиши мне",
            "Люблю прямолинейных 💋 давай в директ",
            "Горячо! 🔥 Продолжим общение?",
        ],
    },
}


class CommentAnalyzer:

    def detect_gender(self, username: str, first_name: str = "") -> str:
        """Определение пола по имени пользователя"""
        name = first_name or username.split(".")[0].split("_")[0]
        name = name.capitalize()

        result = _gender_detector.get_gender(name)

        gender_map = {
            "male": "male",
            "mostly_male": "male",
            "female": "female",
            "mostly_female": "female",
            "andy": "unknown",
            "unknown": "unknown",
        }

        return gender_map.get(result, "unknown")

    def detect_country(self, username: str) -> str:
        """Базовое определение страны по паттернам имени"""
        name_lower = username.lower()

        # Простая эвристика по паттернам имён
        ru_patterns = ["ov", "ev", "ova", "eva", "ski", "skaya", "enko", "uk", "yuk"]
        en_patterns = ["smith", "jones", "john", "mike", "chris"]

        for p in ru_patterns:
            if name_lower.endswith(p):
                return "RU"
        for p in en_patterns:
            if p in name_lower:
                return "US"

        return "unknown"

    def generate_response(self, style: str, gender: str) -> str:
        """Генерация ответа по стилю и полу"""
        templates = RESPONSE_TEMPLATES.get(style, RESPONSE_TEMPLATES["intriguing"])
        gender_key = gender if gender in templates else "male"
        responses = templates.get(gender_key, templates["male"])
        return random.choice(responses)

    async def track_comment(
        self,
        account_id: UUID,
        platform: str,
        post_url: str,
        commenter_username: str,
        commenter_user_id: str,
        comment_text: str,
        first_name: str = "",
    ) -> TrackedComment:
        """Сохранение комментария и планирование ответа"""
        gender = self.detect_gender(commenter_username, first_name)
        country = self.detect_country(commenter_username)

        async with async_session_factory() as db:
            comment = TrackedComment(
                account_id=account_id,
                platform=platform,
                post_url=post_url,
                commenter_username=commenter_username,
                commenter_user_id=commenter_user_id,
                commenter_gender=gender,
                commenter_country=country,
                commenter_analysis={"first_name": first_name},
                comment_text=comment_text,
                response_status="pending",
            )
            db.add(comment)
            await db.commit()
            await db.refresh(comment)

        logger.info("comment.tracked", platform=platform, commenter=commenter_username, gender=gender)
        return comment

    async def process_pending_comments(self, style: str = "intriguing", gender_filter: str = "male"):
        """Обработка ожидающих ответа комментариев"""
        async with async_session_factory() as db:
            query = select(TrackedComment).where(
                TrackedComment.response_status == "pending",
            )
            if gender_filter != "all":
                query = query.where(TrackedComment.commenter_gender == gender_filter)

            result = await db.execute(query.limit(50))
            comments = result.scalars().all()

            for comment in comments:
                response_text = self.generate_response(style, comment.commenter_gender or "unknown")

                # Задержка 40-70 минут
                delay_minutes = random.randint(40, 70)
                scheduled_at = datetime.utcnow() + timedelta(minutes=delay_minutes)

                comment.response_text = response_text
                comment.response_style = style
                comment.response_status = "scheduled"
                comment.response_scheduled_at = scheduled_at

                logger.info(
                    "comment.response_scheduled",
                    commenter=comment.commenter_username,
                    delay_min=delay_minutes,
                    style=style,
                )

            await db.commit()

        return len(comments)

    async def send_scheduled_responses(self):
        """Отправка запланированных ответов (вызывается из APScheduler)"""
        async with async_session_factory() as db:
            result = await db.execute(
                select(TrackedComment).where(
                    TrackedComment.response_status == "scheduled",
                    TrackedComment.response_scheduled_at <= datetime.utcnow(),
                ).limit(20)
            )
            comments = result.scalars().all()

            for comment in comments:
                # Создание задачи на ответ через task_dispatcher
                await redis_client.add_task("chimera:tasks", {
                    "task_type": "comment",
                    "account_id": str(comment.account_id),
                    "payload": {
                        "post_url": comment.post_url,
                        "response_text": comment.response_text,
                        "commenter_username": comment.commenter_username,
                    },
                })

                comment.response_status = "sent"
                comment.response_sent_at = datetime.utcnow()

                logger.info("comment.response_sent", commenter=comment.commenter_username)

            await db.commit()

        return len(comments)


comment_analyzer = CommentAnalyzer()
