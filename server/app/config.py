"""
Конфигурация приложения Chimera v5.0.
Загружает переменные из .env через Pydantic Settings.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Application
    app_version: str = "5.0.0"
    app_name: str = "Chimera"
    debug: bool = False
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://chimera:chimera_secret_2024@postgres:5432/chimera_db"

    # Redis
    redis_url: str = "redis://:redis_secret_2024@redis:6379/0"
    redis_password: str = "redis_secret_2024"

    # JWT
    secret_key: str = "chimera-jwt-secret-key-change-in-production-2024"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # 2Captcha
    twocaptcha_api_key: str = ""

    # LLM
    llm_provider: str = "openai"
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Telegram Bot
    bot_token: str = "ВСТАВЬТЕ_ВАШ_ТОКЕН_СЮДА"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
