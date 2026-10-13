"""Fetch auth/verification codes from email via IMAP."""

from __future__ import annotations

import asyncio
import email as email_lib
import imaplib
import logging
import re
import time

logger = logging.getLogger("chimera.email_sync")

IMAP_SERVERS: dict[str, str] = {
    "gmail.com": "imap.gmail.com",
    "googlemail.com": "imap.gmail.com",
    "outlook.com": "outlook.office365.com",
    "hotmail.com": "outlook.office365.com",
    "yahoo.com": "imap.mail.yahoo.com",
    "mail.ru": "imap.mail.ru",
    "yandex.ru": "imap.yandex.ru",
    "icloud.com": "imap.mail.me.com",
}

PLATFORM_SENDERS: dict[str, list[str]] = {
    "instagram": ["security@mail.instagram.com", "no-reply@mail.instagram.com"],
    "tiktok": ["no-reply@tiktok.com"],
    "facebook": ["security@facebookmail.com", "notification@facebookmail.com"],
    "twitter": ["info@x.com", "verify@twitter.com"],
    "linkedin": ["security-noreply@linkedin.com"],
}


class EmailSync:
    async def fetch_auth_code(
        self, addr: str, pwd: str, platform: str, timeout: int = 120,
    ) -> str | None:
        domain = addr.split("@")[1].lower()
        server = IMAP_SERVERS.get(domain, f"imap.{domain}")
        senders = PLATFORM_SENDERS.get(platform, [])

        start = time.monotonic()
        while time.monotonic() - start < timeout:
            try:
                code = await asyncio.to_thread(
                    self._check_mailbox, server, addr, pwd, senders,
                )
                if code:
                    return code
            except Exception:
                logger.debug("IMAP check failed for %s", addr, exc_info=True)
            await asyncio.sleep(5)
        return None

    def _check_mailbox(
        self, server: str, addr: str, pwd: str, senders: list[str],
    ) -> str | None:
        mail = imaplib.IMAP4_SSL(server)
        try:
            mail.login(addr, pwd)
            mail.select("inbox")
            _, msgs = mail.search(None, "(UNSEEN)")
            if not msgs[0]:
                return None
            for num in reversed(msgs[0].split()):
                _, data = mail.fetch(num, "(RFC822)")
                msg = email_lib.message_from_bytes(data[0][1])
                sender = msg.get("From", "").lower()
                if senders and not any(s in sender for s in senders):
                    continue
                body = self._get_body(msg)
                code = self._extract_code(body)
                if code:
                    return code
            return None
        finally:
            try:
                mail.logout()
            except Exception:
                pass

    def _get_body(self, msg: email_lib.message.Message) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                if ct in ("text/plain", "text/html"):
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode(errors="ignore")
        raw = msg.get_payload(decode=True)
        return raw.decode(errors="ignore") if raw else ""

    def _extract_code(self, text: str) -> str | None:
        m = re.search(r"(?<!\d)(\d{6})(?!\d)", text)
        if m:
            return m.group(1)
        m = re.search(r"(?<!\d)(\d{8})(?!\d)", text)
        if m:
            return m.group(1)
        m = re.search(
            r"(?:code|код|verify|confirmation)[:\s]+(\d{4,8})", text, re.I,
        )
        if m:
            return m.group(1)
        return None
