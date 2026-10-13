"""Centralised logging with rotating file handler and JSON formatter."""
from __future__ import annotations

import json
import logging
import os
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            entry["exc_info"] = traceback.format_exception(*record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


_LOG_DIR = os.environ.get("CHIMERA_LOG_DIR", os.path.join(os.environ.get("CHIMERA_DATA_DIR", "."), "logs"))
_configured = False


def _ensure_dir() -> str:
    os.makedirs(_LOG_DIR, exist_ok=True)
    return _LOG_DIR


def get_logger(name: str) -> logging.Logger:
    global _configured
    logger = logging.getLogger(name)
    if not _configured:
        _configured = True
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        log_dir = _ensure_dir()
        fh = RotatingFileHandler(
            os.path.join(log_dir, "chimera.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        fh.setFormatter(JSONFormatter())
        fh.setLevel(logging.INFO)
        root.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s"))
        sh.setLevel(logging.INFO)
        if not root.handlers:
            root.addHandler(sh)
    return logger
