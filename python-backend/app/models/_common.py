"""Shared helpers for models."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone


def new_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    # Naive UTC datetime for SQLAlchemy DateTime columns (which are tz-naive in
    # this schema). Using `replace(tzinfo=None)` keeps storage uniform while we
    # avoid the deprecated `datetime.utcnow()`.
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Crockford base32 (no I/L/O/U) — 12 chars ≈ 60 bits of entropy, comfortably
# unique for any realistic device/account fleet, and easy to read aloud.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"


def _gen_token(n: int = 12) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(n))


def gen_device_code() -> str:
    """Per-device unique code shown to the user (e.g. CHM-ABCD-EFGH-JKMN)."""
    raw = _gen_token(12)
    return f"CHM-{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def gen_account_code() -> str:
    """Per-account unique code (e.g. ACC-ABCD-EFGH-JKMN). Distinct from
    device codes by prefix so a leaked code can never claim the wrong row."""
    raw = _gen_token(12)
    return f"ACC-{raw[:4]}-{raw[4:8]}-{raw[8:]}"
