"""Загрузка и валидация конфигурации бота из переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Настройки приложения."""

    bot_token: str
    log_level: str = "INFO"
    database_url: str = ""
    admin_id: int = 0

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "Не задан BOT_TOKEN. Скопируйте .env.example в .env и укажите "
                "токен, полученный у @BotFather."
            )
        admin_raw = os.getenv("ADMIN_ID", "").strip()
        try:
            admin_id = int(admin_raw) if admin_raw else 0
        except ValueError:
            admin_id = 0
        return cls(
            bot_token=token,
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
            # Railway Postgres обычно даёт DATABASE_URL.
            database_url=os.getenv("DATABASE_URL", "").strip(),
            admin_id=admin_id,
        )
