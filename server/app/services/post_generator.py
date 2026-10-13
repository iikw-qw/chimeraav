"""
Движок автопостинга: SIPR-микширование, карусели, LLM-подписи, видео-Reels.
Зависит от: config.py, database.py, redis_client.py, models/
"""

import asyncio
import hashlib
import json
import os
import random
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import httpx
import structlog
from PIL import Image
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.dataset import Dataset
from app.models.post import Post
from app.models.task import Task
from app.services.redis_client import redis_client

logger = structlog.get_logger(__name__)

# ═══════════════════════════════════════════════════════════════
# SIPR-микширование: равномерное потребление датасетов
# ═══════════════════════════════════════════════════════════════

# Minimum carousel size / Maximum carousel size
CAROUSEL_MIN = 2
CAROUSEL_MAX = 4

# Maximum times a single photo may be reused before full rotation
MAX_REPETITIONS_BEFORE_ROTATION = 3

# Redis key prefix for SIPR wear-leveling counters
SIPR_PREFIX = "chimera:sipr"


class SIPRMixer:
    """
    SIPR (Sequential Interleaved Photo Rotation) — алгоритм равномерного
    потребления фотографий из нескольких датасетов.
    Каждый датасет расходуется поочерёдно; внутри датасета фото выбираются
    по принципу wear-leveling: наименее использованные идут первыми.
    Повторы контролируются: фото не может повториться больше
    MAX_REPETITIONS_BEFORE_ROTATION раз, пока остальные не будут использованы.
    """

    def __init__(self, redis: Any = None):
        self._redis = redis or redis_client

    async def _get_usage_map(self, dataset_id: UUID) -> Dict[str, int]:
        """Получить карту использования фотографий из Redis."""
        key = f"{SIPR_PREFIX}:{dataset_id}:usage"
        raw = await self._redis.hgetall(key)
        return {k: int(v) if isinstance(v, (str, int)) else 0 for k, v in raw.items()}

    async def _increment_usage(self, dataset_id: UUID, photo_paths: List[str]) -> None:
        """Увеличить счётчик использования для выбранных фото."""
        key = f"{SIPR_PREFIX}:{dataset_id}:usage"
        for path in photo_paths:
            current = await self._redis.hget(key, path)
            count = (int(current) if current else 0) + 1
            await self._redis.hset(key, path, str(count))

    async def _get_round_robin_index(self, user_id: UUID) -> int:
        """Текущий индекс round-robin для чередования датасетов."""
        key = f"{SIPR_PREFIX}:rr:{user_id}"
        val = await self._redis.get_cache(key)
        return int(val) if val else 0

    async def _advance_round_robin(self, user_id: UUID, total_datasets: int) -> None:
        """Сдвинуть индекс round-robin на следующий датасет."""
        key = f"{SIPR_PREFIX}:rr:{user_id}"
        current = await self._get_round_robin_index(user_id)
        next_idx = (current + 1) % max(total_datasets, 1)
        await self._redis.set_cache(key, next_idx, ttl=86400 * 30)

    def _select_least_used(
        self, photos: List[str], usage_map: Dict[str, int], count: int
    ) -> List[str]:
        """
        Wear-leveling: выбрать `count` наименее использованных фотографий.
        При равном счётчике — случайный порядок для разнообразия.
        """
        scored = [(p, usage_map.get(p, 0)) for p in photos]
        # Перемешиваем для случайного выбора среди фото с одинаковым use count
        random.shuffle(scored)
        scored.sort(key=lambda x: x[1])

        # Проверяем порог повторов — если минимальное использование >= порога,
        # значит все фото прошли полный цикл, разрешаем следующий раунд
        selected = []
        for path, use_count in scored:
            if len(selected) >= count:
                break
            if use_count >= MAX_REPETITIONS_BEFORE_ROTATION:
                min_use = scored[0][1] if scored else 0
                if use_count > min_use:
                    continue
            selected.append(path)

        # Если набрали меньше нужного — добираем из оставшихся
        if len(selected) < count:
            remaining = [p for p, _ in scored if p not in selected]
            selected.extend(remaining[: count - len(selected)])

        return selected[:count]

    async def pick_photos(
        self,
        db: AsyncSession,
        user_id: UUID,
        dataset_ids: List[UUID],
        count: int = 1,
    ) -> Tuple[UUID, List[str]]:
        """
        Выбрать фотографии с SIPR-микшированием.
        Возвращает (dataset_id, [пути к фото]).
        """
        if not dataset_ids:
            raise ValueError("Нет доступных датасетов")

        # Round-robin: выбрать датасет
        rr_idx = await self._get_round_robin_index(user_id)
        ds_idx = rr_idx % len(dataset_ids)
        chosen_ds_id = dataset_ids[ds_idx]

        # Загрузить фотографии датасета
        result = await db.execute(select(Dataset).where(Dataset.id == chosen_ds_id))
        dataset = result.scalar_one_or_none()
        if not dataset or not dataset.photos:
            raise ValueError(f"Датасет {chosen_ds_id} пуст или не найден")

        photos: List[str] = dataset.photos

        # Wear-leveling: выбрать наименее использованные
        usage_map = await self._get_usage_map(chosen_ds_id)
        selected = self._select_least_used(photos, usage_map, count)

        # Обновить счётчики
        await self._increment_usage(chosen_ds_id, selected)
        await self._advance_round_robin(user_id, len(dataset_ids))

        await logger.ainfo(
            "sipr_photos_selected",
            dataset_id=str(chosen_ds_id),
            selected_count=len(selected),
            total_pool=len(photos),
        )

        return chosen_ds_id, selected


# ═══════════════════════════════════════════════════════════════
# Семантическая группировка для каруселей
# ═══════════════════════════════════════════════════════════════


def _image_signature(path: str) -> str:
    """
    Быстрая хеш-сигнатура изображения для группировки.
    Используем thumbnail 8x8 → средний цвет → hex-строка.
    """
    try:
        with Image.open(path) as img:
            thumb = img.resize((8, 8)).convert("RGB")
            pixels = list(thumb.getdata())
            avg_r = sum(p[0] for p in pixels) // len(pixels)
            avg_g = sum(p[1] for p in pixels) // len(pixels)
            avg_b = sum(p[2] for p in pixels) // len(pixels)
            return f"{avg_r:02x}{avg_g:02x}{avg_b:02x}"
    except Exception:
        return hashlib.md5(path.encode()).hexdigest()[:6]


def _color_distance(sig_a: str, sig_b: str) -> float:
    """Евклидово расстояние между цветовыми сигнатурами."""
    try:
        ra, ga, ba = int(sig_a[0:2], 16), int(sig_a[2:4], 16), int(sig_a[4:6], 16)
        rb, gb, bb = int(sig_b[0:2], 16), int(sig_b[2:4], 16), int(sig_b[4:6], 16)
        return ((ra - rb) ** 2 + (ga - gb) ** 2 + (ba - bb) ** 2) ** 0.5
    except (ValueError, IndexError):
        return 999.0


def group_carousel_photos(
    photo_paths: List[str], carousel_size: int = 0
) -> List[str]:
    """
    Семантическая группировка: выбрать `carousel_size` фото, наиболее
    похожих друг на друга по цветовой палитре.
    Если carousel_size == 0, автоматически выбирается CAROUSEL_MIN..CAROUSEL_MAX.
    """
    if carousel_size <= 0:
        carousel_size = random.randint(CAROUSEL_MIN, CAROUSEL_MAX)
    carousel_size = min(carousel_size, len(photo_paths))

    if len(photo_paths) <= carousel_size:
        return photo_paths

    # Вычислить сигнатуры
    sigs = {p: _image_signature(p) for p in photo_paths}

    # Жадный алгоритм: начать с первого фото, добавлять ближайшее
    selected = [photo_paths[0]]
    remaining = set(photo_paths[1:])

    while len(selected) < carousel_size and remaining:
        last_sig = sigs[selected[-1]]
        best_path = min(remaining, key=lambda p: _color_distance(last_sig, sigs[p]))
        selected.append(best_path)
        remaining.discard(best_path)

    return selected


# ═══════════════════════════════════════════════════════════════
# LLM-генерация подписей (OpenAI / Anthropic)
# ═══════════════════════════════════════════════════════════════


class LLMCaptionGenerator:
    """
    Генерация подписей к постам через LLM.
    Поддерживает OpenAI (gpt-4o-mini) и Anthropic (claude-3-5-haiku) через конфиг.
    """

    # Системный промпт для генерации подписей
    SYSTEM_PROMPT = (
        "Ты — копирайтер для Instagram. Напиши подпись к посту. "
        "Стиль: живой, вовлекающий, с эмоциями. Длина: 1-3 предложения. "
        "Добавь 3-5 релевантных хештегов. Не используй кавычки вокруг подписи."
    )

    def __init__(self, provider: Optional[str] = None):
        self._provider = provider or settings.llm_provider

    async def generate(
        self,
        context: str,
        style: str = "engaging",
        language: str = "ru",
    ) -> str:
        """
        Сгенерировать подпись к посту.
        context — описание фото/контекст.
        style — стиль подписи (engaging, minimal, storytelling).
        """
        user_prompt = (
            f"Контекст фото: {context}\n"
            f"Стиль подписи: {style}\n"
            f"Язык: {language}"
        )

        if self._provider == "anthropic":
            return await self._generate_anthropic(user_prompt)
        else:
            return await self._generate_openai(user_prompt)

    async def _generate_openai(self, user_prompt: str) -> str:
        """Запрос к OpenAI Chat Completions API."""
        if not settings.openai_api_key:
            await logger.awarning("openai_api_key_missing")
            return self._fallback_caption()

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 300,
            "temperature": 0.8,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                caption = data["choices"][0]["message"]["content"].strip()
                await logger.ainfo("llm_caption_generated", provider="openai", length=len(caption))
                return caption
        except Exception as exc:
            await logger.aerror("openai_caption_error", error=str(exc))
            return self._fallback_caption()

    async def _generate_anthropic(self, user_prompt: str) -> str:
        """Запрос к Anthropic Messages API."""
        if not settings.anthropic_api_key:
            await logger.awarning("anthropic_api_key_missing")
            return self._fallback_caption()

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 300,
            "system": self.SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                caption = data["content"][0]["text"].strip()
                await logger.ainfo("llm_caption_generated", provider="anthropic", length=len(caption))
                return caption
        except Exception as exc:
            await logger.aerror("anthropic_caption_error", error=str(exc))
            return self._fallback_caption()

    @staticmethod
    def _fallback_caption() -> str:
        """Запасная подпись, если LLM недоступен."""
        fallbacks = [
            "Новый день — новые возможности",
            "Жизнь прекрасна в каждом моменте",
            "Ловлю моменты, создаю воспоминания",
            "Каждый день — это подарок",
            "Наслаждаюсь каждым мгновением",
        ]
        tags = ["#lifestyle", "#mood", "#vibes", "#moment", "#instagood"]
        caption = random.choice(fallbacks)
        selected_tags = random.sample(tags, k=random.randint(3, 5))
        return f"{caption}\n\n{' '.join(selected_tags)}"


# ═══════════════════════════════════════════════════════════════
# FFmpeg: конвертация фото → Reels-видео
# ═══════════════════════════════════════════════════════════════


class ReelsVideoConverter:
    """
    Конвертация набора фотографий в видео формата Reels (9:16, 1080x1920).
    Каждое фото показывается 2-4 секунды с плавным переходом.
    Требует FFmpeg в PATH.
    """

    # Output resolution for Instagram Reels (9:16 aspect ratio)
    WIDTH = 1080
    HEIGHT = 1920
    FPS = 30

    # Duration each photo is shown (seconds)
    PHOTO_DURATION_MIN = 2.0
    PHOTO_DURATION_MAX = 4.0

    # Crossfade transition duration (seconds)
    TRANSITION_DURATION = 0.5

    @staticmethod
    def _check_ffmpeg() -> bool:
        """Check if FFmpeg is available in PATH."""
        return shutil.which("ffmpeg") is not None

    async def convert(
        self,
        photo_paths: List[str],
        output_path: Optional[str] = None,
        music_path: Optional[str] = None,
    ) -> str:
        """
        Конвертировать фотографии в видео-Reels.
        Возвращает путь к итоговому .mp4 файлу.
        """
        if not self._check_ffmpeg():
            raise RuntimeError("FFmpeg не найден в PATH. Установите FFmpeg.")

        if not photo_paths:
            raise ValueError("Нет фотографий для конвертации")

        if output_path is None:
            output_dir = tempfile.mkdtemp(prefix="chimera_reels_")
            output_path = os.path.join(output_dir, f"reels_{uuid.uuid4().hex[:8]}.mp4")

        # Подготовить временные файлы с нормализованным размером
        prepared = await self._prepare_photos(photo_paths)

        try:
            # Собрать FFmpeg фильтр
            filter_complex, input_args = self._build_filter(prepared)

            cmd = ["ffmpeg", "-y"]
            cmd.extend(input_args)

            if music_path and os.path.isfile(music_path):
                cmd.extend(["-i", music_path])

            cmd.extend([
                "-filter_complex", filter_complex,
                "-map", "[outv]",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-r", str(self.FPS),
                "-movflags", "+faststart",
            ])

            # Добавить аудиодорожку если есть музыка
            if music_path and os.path.isfile(music_path):
                audio_idx = len(prepared)
                cmd.extend([
                    "-map", f"{audio_idx}:a",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-shortest",
                ])

            cmd.append(output_path)

            # Запуск FFmpeg в отдельном потоке, чтобы не блокировать event loop
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                await logger.aerror("ffmpeg_error", returncode=process.returncode, stderr=error_msg[:500])
                raise RuntimeError(f"FFmpeg завершился с ошибкой: {error_msg[:200]}")

            await logger.ainfo(
                "reels_video_created",
                output=output_path,
                photos_count=len(photo_paths),
            )
            return output_path

        finally:
            # Удалить временные нормализованные фото
            for tmp_path in prepared:
                if tmp_path not in photo_paths:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

    async def _prepare_photos(self, photo_paths: List[str]) -> List[str]:
        """
        Нормализовать фото: привести к 1080x1920, добавить padding при необходимости.
        Возвращает пути к подготовленным файлам.
        """
        prepared = []
        for path in photo_paths:
            try:
                with Image.open(path) as img:
                    img = img.convert("RGB")
                    # Вписать в 1080x1920 с сохранением пропорций
                    img.thumbnail((self.WIDTH, self.HEIGHT), Image.LANCZOS)
                    # Создать фон нужного размера
                    background = Image.new("RGB", (self.WIDTH, self.HEIGHT), (0, 0, 0))
                    offset_x = (self.WIDTH - img.width) // 2
                    offset_y = (self.HEIGHT - img.height) // 2
                    background.paste(img, (offset_x, offset_y))

                    tmp_path = os.path.join(
                        tempfile.gettempdir(),
                        f"chimera_prep_{uuid.uuid4().hex[:8]}.jpg",
                    )
                    background.save(tmp_path, "JPEG", quality=95)
                    prepared.append(tmp_path)
            except Exception as exc:
                await logger.awarning("photo_prepare_error", path=path, error=str(exc))
                # Используем оригинал как fallback
                prepared.append(path)

        return prepared

    def _build_filter(self, photo_paths: List[str]) -> Tuple[str, List[str]]:
        """
        Построить FFmpeg filter_complex для слайдшоу с переходами.
        Возвращает (filter_string, input_args).
        """
        input_args = []
        filter_parts = []
        durations = []

        for i, path in enumerate(photo_paths):
            duration = random.uniform(self.PHOTO_DURATION_MIN, self.PHOTO_DURATION_MAX)
            durations.append(duration)
            input_args.extend([
                "-loop", "1",
                "-t", f"{duration:.2f}",
                "-i", path,
            ])
            # Scale + pad each input to target resolution
            filter_parts.append(
                f"[{i}:v]scale={self.WIDTH}:{self.HEIGHT}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={self.WIDTH}:{self.HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
                f"setsar=1,fps={self.FPS}[v{i}]"
            )

        # Конкатенация с crossfade переходами
        if len(photo_paths) == 1:
            filter_parts.append(f"[v0]copy[outv]")
        else:
            # Построить цепочку xfade переходов
            current_label = "v0"
            offset = durations[0] - self.TRANSITION_DURATION

            for i in range(1, len(photo_paths)):
                out_label = "outv" if i == len(photo_paths) - 1 else f"xf{i}"
                filter_parts.append(
                    f"[{current_label}][v{i}]xfade=transition=fade:"
                    f"duration={self.TRANSITION_DURATION:.2f}:"
                    f"offset={offset:.2f}[{out_label}]"
                )
                current_label = out_label
                if i < len(photo_paths) - 1:
                    offset += durations[i] - self.TRANSITION_DURATION

        filter_complex = ";".join(filter_parts)
        return filter_complex, input_args


# ═══════════════════════════════════════════════════════════════
# Главный движок: собирает всё вместе
# ═══════════════════════════════════════════════════════════════


class PostGenerator:
    """
    Движок автопостинга.
    Объединяет SIPR-микширование, карусели, LLM-подписи и Reels-видео.
    Создаёт задачу на публикацию через устройство.
    """

    def __init__(self):
        self._mixer = SIPRMixer()
        self._llm = LLMCaptionGenerator()
        self._video = ReelsVideoConverter()

    async def generate_photo_post(
        self,
        db: AsyncSession,
        user_id: UUID,
        account_id: UUID,
        dataset_ids: List[UUID],
        caption_context: str = "",
        caption_style: str = "engaging",
        language: str = "ru",
    ) -> Post:
        """
        Сгенерировать фото-пост (одно фото).
        Создаёт пост в БД и задачу на публикацию.
        """
        dataset_id, photos = await self._mixer.pick_photos(db, user_id, dataset_ids, count=1)

        # Генерация подписи
        caption = await self._llm.generate(
            context=caption_context or "Фотопост для Instagram",
            style=caption_style,
            language=language,
        )

        # Создать запись поста
        post = Post(
            id=uuid.uuid4(),
            user_id=user_id,
            account_id=account_id,
            dataset_id=dataset_id,
            photos=photos,
            caption=caption,
            platform="instagram",
            status="ready",
            created_at=datetime.utcnow(),
        )
        db.add(post)
        await db.flush()

        # Создать задачу на публикацию
        await self._create_publish_task(db, user_id, account_id, post)

        await logger.ainfo(
            "photo_post_generated",
            post_id=str(post.id),
            dataset_id=str(dataset_id),
            photos_count=1,
        )

        return post

    async def generate_carousel_post(
        self,
        db: AsyncSession,
        user_id: UUID,
        account_id: UUID,
        dataset_ids: List[UUID],
        carousel_size: int = 0,
        caption_context: str = "",
        caption_style: str = "engaging",
        language: str = "ru",
    ) -> Post:
        """
        Сгенерировать пост-карусель (2-4 фото с семантической группировкой).
        """
        if carousel_size <= 0:
            carousel_size = random.randint(CAROUSEL_MIN, CAROUSEL_MAX)

        # Выбрать фото с запасом для группировки
        pool_size = min(carousel_size * 3, 12)
        dataset_id, photo_pool = await self._mixer.pick_photos(
            db, user_id, dataset_ids, count=pool_size
        )

        # Семантическая группировка — выбрать наиболее согласованные фото
        carousel_photos = group_carousel_photos(photo_pool, carousel_size)

        # Генерация подписи
        caption = await self._llm.generate(
            context=caption_context or f"Карусель из {len(carousel_photos)} фотографий для Instagram",
            style=caption_style,
            language=language,
        )

        post = Post(
            id=uuid.uuid4(),
            user_id=user_id,
            account_id=account_id,
            dataset_id=dataset_id,
            photos=carousel_photos,
            caption=caption,
            platform="instagram",
            status="ready",
            created_at=datetime.utcnow(),
        )
        db.add(post)
        await db.flush()

        await self._create_publish_task(db, user_id, account_id, post)

        await logger.ainfo(
            "carousel_post_generated",
            post_id=str(post.id),
            carousel_size=len(carousel_photos),
        )

        return post

    async def generate_reels_post(
        self,
        db: AsyncSession,
        user_id: UUID,
        account_id: UUID,
        dataset_ids: List[UUID],
        photo_count: int = 5,
        music_path: Optional[str] = None,
        caption_context: str = "",
        caption_style: str = "engaging",
        language: str = "ru",
    ) -> Post:
        """
        Сгенерировать Reels-видео из фотографий.
        Конвертирует набор фото в .mp4 через FFmpeg.
        """
        dataset_id, photos = await self._mixer.pick_photos(
            db, user_id, dataset_ids, count=photo_count
        )

        # Конвертировать в видео
        video_path = await self._video.convert(photos, music_path=music_path)

        # Генерация подписи
        caption = await self._llm.generate(
            context=caption_context or "Reels-видео для Instagram",
            style=caption_style,
            language=language,
        )

        post = Post(
            id=uuid.uuid4(),
            user_id=user_id,
            account_id=account_id,
            dataset_id=dataset_id,
            photos=photos,
            caption=caption,
            platform="instagram",
            status="ready",
            created_at=datetime.utcnow(),
        )
        db.add(post)
        await db.flush()

        # Задача на публикацию Reels с путём к видео
        await self._create_publish_task(
            db, user_id, account_id, post,
            extra_payload={"video_path": video_path, "post_type": "reels"},
        )

        await logger.ainfo(
            "reels_post_generated",
            post_id=str(post.id),
            video_path=video_path,
            photos_count=len(photos),
        )

        return post

    async def _create_publish_task(
        self,
        db: AsyncSession,
        user_id: UUID,
        account_id: UUID,
        post: Post,
        extra_payload: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """
        Создать задачу на публикацию поста на устройстве.
        Задача попадает в очередь и будет выполнена агентом на устройстве.
        """
        payload: Dict[str, Any] = {
            "post_id": str(post.id),
            "photos": post.photos,
            "caption": post.caption,
            "platform": post.platform,
            "post_type": extra_payload.get("post_type", "photo") if extra_payload else "photo",
        }
        if extra_payload:
            payload.update(extra_payload)

        # Найти device_id через аккаунт
        from app.models.account import SocialAccount
        result = await db.execute(
            select(SocialAccount.device_id).where(SocialAccount.id == account_id)
        )
        device_id = result.scalar_one_or_none()

        task = Task(
            id=uuid.uuid4(),
            user_id=user_id,
            device_id=device_id,
            account_id=account_id,
            task_type="publish_post",
            status="pending",
            priority=5,
            payload=payload,
            created_at=datetime.utcnow(),
        )
        db.add(task)
        await db.flush()

        # Отправить задачу в Redis Stream для обработки агентом на устройстве
        await redis_client.add_task(
            "chimera:tasks:publish",
            {
                "task_id": str(task.id),
                "device_id": str(device_id) if device_id else None,
                "account_id": str(account_id),
                "payload": payload,
            },
        )

        await logger.ainfo(
            "publish_task_created",
            task_id=str(task.id),
            post_id=str(post.id),
        )

        return task

    async def batch_generate(
        self,
        db: AsyncSession,
        user_id: UUID,
        account_ids: List[UUID],
        dataset_ids: List[UUID],
        post_type: str = "photo",
        count_per_account: int = 1,
        caption_style: str = "engaging",
        language: str = "ru",
    ) -> List[Post]:
        """
        Пакетная генерация постов для нескольких аккаунтов.
        Распределяет датасеты равномерно через SIPR.
        """
        posts: List[Post] = []

        for account_id in account_ids:
            for _ in range(count_per_account):
                try:
                    if post_type == "carousel":
                        post = await self.generate_carousel_post(
                            db, user_id, account_id, dataset_ids,
                            caption_style=caption_style, language=language,
                        )
                    elif post_type == "reels":
                        post = await self.generate_reels_post(
                            db, user_id, account_id, dataset_ids,
                            caption_style=caption_style, language=language,
                        )
                    else:
                        post = await self.generate_photo_post(
                            db, user_id, account_id, dataset_ids,
                            caption_style=caption_style, language=language,
                        )
                    posts.append(post)
                except Exception as exc:
                    await logger.aerror(
                        "batch_generate_error",
                        account_id=str(account_id),
                        error=str(exc),
                    )

        await logger.ainfo(
            "batch_generation_complete",
            total_posts=len(posts),
            accounts_count=len(account_ids),
        )

        return posts
