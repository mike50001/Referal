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

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "Не задан BOT_TOKEN. Скопируйте .env.example в .env и укажите "
                "токен, полученный у @BotFather."
            )
        return cls(
            bot_token=token,
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        )
