"""Automatic account registration on social media platforms."""

from __future__ import annotations

import asyncio
import imaplib
import email as email_lib
import logging
import random
import re
import string
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import SessionLocal
from app.models.account import Account
from app.models.account_registration import AccountRegistration
from app.services.human_cursor import human_cursor, HumanCursor
from app.services.ui_recognizer import ui_recognizer

logger = logging.getLogger("chimera.account_registrator")

IMAP_SERVERS = {
    "gmail.com": "imap.gmail.com",
    "googlemail.com": "imap.gmail.com",
    "outlook.com": "imap-mail.outlook.com",
    "hotmail.com": "imap-mail.outlook.com",
    "live.com": "imap-mail.outlook.com",
    "mail.ru": "imap.mail.ru",
    "yandex.ru": "imap.yandex.ru",
    "yandex.com": "imap.yandex.com",
    "yahoo.com": "imap.mail.yahoo.com",
    "icloud.com": "imap.mail.me.com",
}

FIRST_NAMES = [
    "Emma", "Liam", "Olivia", "Noah", "Ava", "Oliver", "Sophia", "Elijah",
    "Isabella", "James", "Mia", "William", "Charlotte", "Benjamin", "Amelia",
    "Lucas", "Harper", "Henry", "Evelyn", "Alexander", "Luna", "Daniel",
    "Ella", "Matthew", "Scarlett", "Jack", "Grace", "Samuel", "Lily",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Anderson", "Taylor", "Thomas", "Moore",
    "Jackson", "Martin", "Lee", "Thompson", "White", "Harris", "Clark",
]

PLATFORM_VERIFICATION_SENDERS = {
    "instagram": ["security@mail.instagram.com", "no-reply@mail.instagram.com"],
    "facebook": ["notification@facebookmail.com", "security@facebookmail.com"],
    "twitter": ["info@x.com", "verify@twitter.com"],
    "tiktok": ["no-reply@tiktok.com"],
    "linkedin": ["security-noreply@linkedin.com"],
    "reddit": ["noreply@reddit.com", "noreply@redditmail.com"],
    "vk": ["support@vk.com", "noreply@vk.com"],
}


class AccountRegistrator:
    """Registers accounts on social platforms using UI automation."""

    async def register_account(
        self,
        device_id: str,
        platform: str,
        email_addr: str,
        email_password: str,
        device_serial: str | None = None,
        on_progress: Any = None,
    ) -> dict[str, Any]:
        reg_id = None
        try:
            async with SessionLocal() as session:
                reg = AccountRegistration(
                    email=email_addr,
                    email_password_encrypted=email_password,
                    platform=platform,
                    device_id=device_id,
                    status="in_progress",
                )
                session.add(reg)
                await session.commit()
                await session.refresh(reg)
                reg_id = reg.id

            await self._emit(on_progress, reg_id, "starting", "Открываем приложение...")

            fullname = self._generate_fullname()
            username = self._generate_username(platform, fullname)

            await self._emit(on_progress, reg_id, "navigating", "Переходим к регистрации...")

            if device_serial:
                elements = await ui_recognizer.find_all_elements(
                    platform, "register", device_serial=device_serial
                )
            else:
                elements = {}

            await self._emit(on_progress, reg_id, "input", "Вводим данные...")

            if device_serial:
                cursor = HumanCursor()

                email_el = elements.get("email_field")
                if email_el and "bounds" in email_el:
                    bounds = email_el["bounds"]
                    cx = bounds.get("cx", (bounds.get("x1", 0) + bounds.get("x2", 0)) // 2)
                    cy = bounds.get("cy", (bounds.get("y1", 0) + bounds.get("y2", 0)) // 2)
                    tap = cursor.tap(cx, cy)
                    await self._execute_touch(device_serial, tap)
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                    text_actions = cursor.type_text(email_addr)
                    await self._execute_typing(device_serial, text_actions)

                await asyncio.sleep(random.uniform(0.5, 1.5))

                password_el = elements.get("password_field")
                if password_el and "bounds" in password_el:
                    bounds = password_el["bounds"]
                    cx = bounds.get("cx", (bounds.get("x1", 0) + bounds.get("x2", 0)) // 2)
                    cy = bounds.get("cy", (bounds.get("y1", 0) + bounds.get("y2", 0)) // 2)
                    tap = cursor.tap(cx, cy)
                    await self._execute_touch(device_serial, tap)
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                    password = self._generate_password()
                    text_actions = cursor.type_text(password)
                    await self._execute_typing(device_serial, text_actions)

                fullname_el = elements.get("fullname_field")
                if fullname_el and "bounds" in fullname_el:
                    bounds = fullname_el["bounds"]
                    cx = bounds.get("cx", (bounds.get("x1", 0) + bounds.get("x2", 0)) // 2)
                    cy = bounds.get("cy", (bounds.get("y1", 0) + bounds.get("y2", 0)) // 2)
                    tap = cursor.tap(cx, cy)
                    await self._execute_touch(device_serial, tap)
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                    text_actions = cursor.type_text(fullname)
                    await self._execute_typing(device_serial, text_actions)

                username_el = elements.get("username_field")
                if username_el and "bounds" in username_el:
                    bounds = username_el["bounds"]
                    cx = bounds.get("cx", (bounds.get("x1", 0) + bounds.get("x2", 0)) // 2)
                    cy = bounds.get("cy", (bounds.get("y1", 0) + bounds.get("y2", 0)) // 2)
                    tap = cursor.tap(cx, cy)
                    await self._execute_touch(device_serial, tap)
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                    text_actions = cursor.type_text(username)
                    await self._execute_typing(device_serial, text_actions)

                next_el = elements.get("next_button")
                if next_el and "bounds" in next_el:
                    bounds = next_el["bounds"]
                    cx = bounds.get("cx", (bounds.get("x1", 0) + bounds.get("x2", 0)) // 2)
                    cy = bounds.get("cy", (bounds.get("y1", 0) + bounds.get("y2", 0)) // 2)
                    tap = cursor.tap(cx, cy)
                    await self._execute_touch(device_serial, tap)

            await self._emit(on_progress, reg_id, "verification", "Проходим верификацию...")

            verification_code = await self._fetch_email_verification_code(
                email_addr, email_password, platform
            )
            if verification_code and device_serial:
                await asyncio.sleep(random.uniform(1.0, 2.0))
                cursor_v = HumanCursor()
                text_actions = cursor_v.type_text(verification_code)
                await self._execute_typing(device_serial, text_actions)

            await self._emit(on_progress, reg_id, "finalizing", "Завершаем регистрацию...")

            async with SessionLocal() as session:
                reg_obj = await session.get(AccountRegistration, reg_id)
                if reg_obj:
                    reg_obj.status = "completed"
                    reg_obj.target_username = username

                account = Account(
                    device_id=device_id,
                    platform=platform,
                    username=username,
                    password_encrypted=email_password,
                    status="active",
                )
                session.add(account)
                await session.commit()
                await session.refresh(account)

            await self._emit(on_progress, reg_id, "done", "Аккаунт создан!")
            return {
                "ok": True,
                "registration_id": reg_id,
                "username": username,
                "platform": platform,
            }

        except Exception as e:
            logger.error("Registration failed: %s", e)
            if reg_id:
                try:
                    async with SessionLocal() as session:
                        reg_obj = await session.get(AccountRegistration, reg_id)
                        if reg_obj:
                            reg_obj.status = "failed"
                            reg_obj.error_message = str(e)
                            await session.commit()
                except Exception:
                    pass
            await self._emit(on_progress, reg_id, "error", f"Ошибка: {e}")
            return {"ok": False, "error": str(e), "registration_id": reg_id}

    async def _fetch_email_verification_code(
        self, email_addr: str, email_password: str, platform: str
    ) -> str | None:
        domain = email_addr.split("@")[-1].lower()
        imap_server = IMAP_SERVERS.get(domain)
        if not imap_server:
            logger.warning("Unknown email domain: %s", domain)
            return None

        try:
            mail = await asyncio.to_thread(
                self._imap_fetch_code, imap_server, email_addr, email_password, platform
            )
            return mail
        except Exception as e:
            logger.error("Email verification fetch failed: %s", e)
            return None

    def _imap_fetch_code(
        self, imap_server: str, email_addr: str, password: str, platform: str
    ) -> str | None:
        try:
            mail = imaplib.IMAP4_SSL(imap_server)
            mail.login(email_addr, password)
            mail.select("INBOX")

            senders = PLATFORM_VERIFICATION_SENDERS.get(platform, [])
            for sender in senders:
                _, messages = mail.search(None, f'FROM "{sender}"')
                msg_nums = messages[0].split()
                if not msg_nums:
                    continue

                _, data = mail.fetch(msg_nums[-1], "(RFC822)")
                msg = email_lib.message_from_bytes(data[0][1])

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                            break
                        elif part.get_content_type() == "text/html":
                            body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

                codes = re.findall(r'\b(\d{4,8})\b', body)
                if codes:
                    mail.logout()
                    return codes[-1]

            mail.logout()
        except Exception as e:
            logger.error("IMAP error: %s", e)
        return None

    def _generate_fullname(self) -> str:
        return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

    def _generate_username(self, platform: str, fullname: str) -> str:
        parts = fullname.lower().split()
        base = parts[0] if parts else "user"
        suffix = random.randint(100, 9999)
        separators = ["", "_", "."]
        sep = random.choice(separators)
        if len(parts) > 1:
            return f"{parts[0]}{sep}{parts[1]}{suffix}"
        return f"{base}{suffix}"

    def _generate_password(self, length: int = 14) -> str:
        chars = string.ascii_letters + string.digits + "!@#$%"
        password = [
            random.choice(string.ascii_uppercase),
            random.choice(string.ascii_lowercase),
            random.choice(string.digits),
            random.choice("!@#$%"),
        ]
        password.extend(random.choices(chars, k=length - 4))
        random.shuffle(password)
        return "".join(password)

    async def _execute_touch(self, serial: str, tap: Any) -> None:
        if hasattr(tap, "path"):
            for point in tap.path[-3:]:
                proc = await asyncio.create_subprocess_exec(
                    "adb", "-s", serial, "shell", "input", "tap",
                    str(point.x), str(point.y),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                await asyncio.sleep(point.delay_ms / 1000)

    async def _execute_typing(self, serial: str, actions: list) -> None:
        for act in actions:
            if hasattr(act, "action"):
                if act.action == "type" and act.char:
                    char = act.char.replace(" ", "%s").replace("'", "\\'")
                    proc = await asyncio.create_subprocess_exec(
                        "adb", "-s", serial, "shell", "input", "text", char,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await proc.communicate()
                elif act.action == "backspace":
                    proc = await asyncio.create_subprocess_exec(
                        "adb", "-s", serial, "shell", "input", "keyevent", "67",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await proc.communicate()
                await asyncio.sleep(act.delay_ms / 1000)

    async def _emit(self, callback: Any, reg_id: str | None, stage: str, message: str) -> None:
        logger.info("[%s] %s: %s", reg_id, stage, message)
        if callback:
            try:
                await callback(reg_id, stage, message)
            except Exception:
                pass


account_registrator = AccountRegistrator()
