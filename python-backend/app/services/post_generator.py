"""Generate social posts — pick photos via SIPR, scrub metadata, draft caption."""

from __future__ import annotations

import os
from typing import Any, Literal

import httpx
from sqlalchemy import select

from app.database import SessionLocal
from app.models.account import Account
from app.models.app_settings import AppSettings
from app.models.post import Post
from app.services.gallery_service import gallery_service
from app.services.metadata_cleaner import metadata_cleaner
from app.services.sipr import SIPRManager, MixStrategy

_DEFAULT_STYLE = "friendly"

MediaKind = Literal["photo", "video"]


class PostGenerator:
    async def generate(
        self,
        account_id: str,
        dataset_id: str,
        platform: str,
        *,
        photo_count: int = 3,
        clean_metadata: bool = True,
        mix_strategy: MixStrategy | None = None,
        media_kind: MediaKind = "photo",
        device_id: str | None = None,
    ) -> dict[str, Any]:
        if mix_strategy is None:
            mix_strategy = await self._mixing_strategy_default()
        sipr = SIPRManager(dataset_id, account_id=account_id)
        photos = await sipr.select_photos(
            count=photo_count,
            strategy=mix_strategy,
            media_kind=media_kind,
        )

        cleaned_results: list[dict[str, Any]] = []
        if clean_metadata and photos and media_kind == "photo":
            for path in photos:
                try:
                    result = await metadata_cleaner.clean_image(path)
                    cleaned_results.append(
                        {"path": path, "ok": True, "detail": result}
                    )
                except Exception as exc:
                    cleaned_results.append(
                        {"path": path, "ok": False, "error": str(exc)}
                    )

        async with SessionLocal() as session:
            account = await session.get(Account, account_id)
            if account is None:
                raise ValueError(f"Account {account_id} not found")
            style = account.posting_style or _DEFAULT_STYLE
            llm_cfg = await self._llm_config(session)
            gallery_publish = await self._gallery_publish_enabled(session)

        caption = await self._generate_caption(platform, style, photos, llm_cfg)

        # Push media onto the account's device so the post is published from
        # the native gallery — same flow a real user would take.
        device_paths: list[str] = []
        target_device_id = device_id or getattr(account, "device_id", None)
        if gallery_publish and target_device_id and photos:
            try:
                device_paths = await gallery_service.push_many(target_device_id, photos)
            except Exception as exc:
                cleaned_results.append({"gallery_push_error": str(exc)})

        async with SessionLocal() as session:
            post = Post(
                account_id=account_id,
                platform=platform,
                photos=photos if media_kind == "photo" else [],
                video_url=photos[0] if (media_kind == "video" and photos) else None,
                caption=caption,
                sipr_dataset_id=dataset_id,
                metadata_cleaned=clean_metadata and media_kind == "photo",
            )
            session.add(post)
            await session.commit()
            await session.refresh(post)

        return {
            "post_id": post.id,
            "photos": photos,
            "device_paths": device_paths,
            "caption": caption,
            "cleaned": cleaned_results,
            "metadata_cleaned": clean_metadata and media_kind == "photo",
            "media_kind": media_kind,
            "mix_strategy": mix_strategy,
            "device_id": target_device_id,
        }

    @staticmethod
    async def _mixing_strategy_default() -> MixStrategy:
        async with SessionLocal() as session:
            stmt = select(AppSettings).where(AppSettings.key == "mixing_strategy")
            row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return "smart"
        v = str(row.value or "smart")
        if v in ("wear", "interleave", "random_offset", "stride", "cross", "smart"):
            return v  # type: ignore[return-value]
        return "smart"

    @staticmethod
    async def _gallery_publish_enabled(session) -> bool:
        stmt = select(AppSettings).where(AppSettings.key == "gallery_publish")
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return True  # default ON so posts flow through the device gallery
        value = row.value
        return bool(value) if not isinstance(value, str) else value.lower() != "false"

    @staticmethod
    async def _llm_config(session) -> dict[str, Any]:
        stmt = select(AppSettings).where(
            AppSettings.key.in_(("llm_api_base", "llm_model", "llm_api_key"))
        )
        rows = list((await session.execute(stmt)).scalars().all())
        settings = {row.key: row.value for row in rows}
        return {
            "api_base": settings.get("llm_api_base")
            or os.environ.get("CHIMERA_LLM_API_BASE")
            or "https://api.openai.com/v1",
            "model": settings.get("llm_model")
            or os.environ.get("CHIMERA_LLM_MODEL")
            or "gpt-4o-mini",
            "api_key": settings.get("llm_api_key")
            or os.environ.get("CHIMERA_LLM_API_KEY")
            or "",
        }

    async def _generate_caption(
        self,
        platform: str,
        style: str,
        photos: list[str],
        cfg: dict[str, Any],
    ) -> str:
        if not cfg.get("api_key"):
            return f"New {style} post for {platform} ✨"

        system_prompt = (
            f"You are a social media copywriter crafting a post for {platform}. "
            f"Match a {style} tone. Write a caption of 1-3 sentences, add 2-5 "
            "relevant hashtags at the end. Output only the caption text."
        )
        user_prompt = (
            f"Compose a caption for {len(photos)} photos on {platform}."
            if photos
            else f"Compose a caption for a {platform} post."
        )

        url = f"{cfg['api_base'].rstrip('/')}/chat/completions"
        payload = {
            "model": cfg["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.8,
            "max_tokens": 180,
        }
        headers = {
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception:
            return f"New {style} post for {platform} ✨"


post_generator = PostGenerator()
