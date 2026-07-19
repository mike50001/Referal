"""Загрузка и валидация конфигурации из переменных окружения."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_chat_id: int
    admin_ids: set[int] = field(default_factory=set)
    markup_percent: float = 0.0  # наценка обменника к рыночному курсу, %

    def is_admin(self, user_id: int) -> bool:
        """Может ли пользователь отвечать клиентам.

        Если список ADMIN_IDS пуст — считаем админом любого, кто пишет
        в admin_chat_id (проверка чата выполняется в хендлере).
        """
        if not self.admin_ids:
            return True
        return user_id in self.admin_ids


def _parse_admin_ids(raw: str | None) -> set[int]:
    if not raw:
        return set()
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part:
            ids.add(int(part))
    return ids


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Не задан BOT_TOKEN. Скопируйте .env.example в .env и укажите токен бота."
        )

    admin_chat_raw = os.getenv("ADMIN_CHAT_ID", "").strip()
    if not admin_chat_raw:
        raise RuntimeError(
            "Не задан ADMIN_CHAT_ID. Укажите ID чата, куда бот будет присылать заявки."
        )
    try:
        admin_chat_id = int(admin_chat_raw)
    except ValueError as exc:
        raise RuntimeError("ADMIN_CHAT_ID должен быть числом.") from exc

    markup_raw = os.getenv("EXCHANGE_MARKUP_PERCENT", "0").strip().replace(",", ".")
    try:
        markup_percent = float(markup_raw) if markup_raw else 0.0
    except ValueError as exc:
        raise RuntimeError("EXCHANGE_MARKUP_PERCENT должен быть числом (например, 2.5).") from exc

    return Config(
        bot_token=token,
        admin_chat_id=admin_chat_id,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS")),
        markup_percent=markup_percent,
    )
