"""Отправка уведомлений в Telegram (об открытии/закрытии сделок).

Если TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID не заданы — уведомления выключены,
бот работает как обычно.
"""
from __future__ import annotations

import logging

import requests

log = logging.getLogger("bot.notify")


class Notifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.enabled = bool(token and chat_id)

    def send(self, text: str) -> None:
        if not self.enabled:
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": text},
                timeout=10,
            )
        except requests.RequestException as e:
            log.warning("Не удалось отправить в Telegram: %s", e)
