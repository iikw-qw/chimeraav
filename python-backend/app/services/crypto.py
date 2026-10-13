"""Simple reversible encoding for email passwords stored in SQLite."""

from __future__ import annotations

import base64


def encrypt(plaintext: str) -> str:
    return base64.b64encode(plaintext.encode("utf-8")).decode("ascii")


def decrypt(ciphertext: str) -> str:
    return base64.b64decode(ciphertext.encode("ascii")).decode("utf-8")
