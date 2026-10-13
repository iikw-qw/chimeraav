"""Application settings."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _platform_data_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return str(Path(base) / "Chimera")
    if sys.platform == "darwin":
        return str(Path.home() / "Library" / "Application Support" / "Chimera")
    xdg = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return str(Path(xdg) / "Chimera")


def _resolved_data_dir() -> str:
    return os.environ.get("CHIMERA_DATA_DIR") or _platform_data_dir()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHIMERA_", extra="ignore")

    data_dir: str = _resolved_data_dir()
    host: str = "127.0.0.1"
    port: int = 17842

    def ensure_dirs(self) -> None:
        root = Path(self.data_dir)
        root.mkdir(parents=True, exist_ok=True)
        for sub in ("datasets", "cleaned", "exports", "backups"):
            (root / sub).mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
