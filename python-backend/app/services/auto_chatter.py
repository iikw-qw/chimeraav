"""Auto-chatter — reply to incoming DMs in English via LLM, dispatch through device."""

from __future__ import annotations

import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select

from app.database import SessionLocal
from app.models.account import Account
from app.models.app_settings import AppSettings
from app.models.task import Task

SYSTEM_PROMPT = (
    "You are a friendly person chatting on social media. "
    "Always respond in ENGLISH regardless of the other person's language. "
    "Keep responses short (1-2 sentences), casual. Don't reveal you are an AI."
)


class AutoChatter:
    """Reply to DMs in English. Language is hard-coded regardless of input."""

    language = "en"

    def __init__(
        self,
        *,
        api_base: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._api_base = api_base
        self._model = model
        self._api_key = api_key

    async def handle_reply(
        self, account_id: str, sender: str, text: str
    ) -> dict[str, Any]:
        config = await self._load_config()
        reply_text = await self._generate_reply(text, config)

        async with SessionLocal() as session:
            account = await session.get(Account, account_id)
            if account is None:
                raise ValueError(f"Account {account_id} not found")

            delay_minutes = random.randint(40, 70)
            scheduled = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)

            task = Task(
                device_id=account.device_id,
                account_id=account_id,
                task_type="send_dm_reply",
                priority=4,
                scheduled_at=scheduled.replace(tzinfo=None),
                payload={
                    "recipient_username": sender,
                    "message_text": reply_text,
                    "language": self.language,
                    "incoming_text": text,
                    "delay_minutes": delay_minutes,
                },
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

        return {
            "task_id": task.id,
            "reply": reply_text,
            "language": self.language,
        }

    async def _load_config(self) -> dict[str, Any]:
        async with SessionLocal() as session:
            stmt = select(AppSettings).where(
                AppSettings.key.in_(("llm_api_base", "llm_model", "llm_api_key"))
            )
            rows = list((await session.execute(stmt)).scalars().all())
        settings = {row.key: row.value for row in rows}
        return {
            "api_base": self._api_base
            or settings.get("llm_api_base")
            or os.environ.get("CHIMERA_LLM_API_BASE")
            or "https://api.openai.com/v1",
            "model": self._model
            or settings.get("llm_model")
            or os.environ.get("CHIMERA_LLM_MODEL")
            or "gpt-4o-mini",
            "api_key": self._api_key
            or settings.get("llm_api_key")
            or os.environ.get("CHIMERA_LLM_API_KEY")
            or "",
        }

    async def _generate_reply(self, text: str, config: dict[str, Any]) -> str:
        api_key = config["api_key"]
        if not api_key:
            return "Hey! Thanks for the message."

        url = f"{config['api_base'].rstrip('/')}/chat/completions"
        payload = {
            "model": config["model"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "temperature": 0.8,
            "max_tokens": 120,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, AttributeError):
            return "Hey! Thanks for the message."


auto_chatter = AutoChatter()
