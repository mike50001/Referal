"""Telegram FAQ-автоответчик (long polling, без внешних тяжёлых зависимостей).

Использует Bot API напрямую через requests: getUpdates -> reply -> sendMessage.
Токен берётся из autoresponder/.env (TELEGRAM_BOT_TOKEN).

Запуск:
    python telegram_bot.py
"""
from __future__ import annotations

import logging
import os
import time

import requests
from dotenv import load_dotenv

from faq_engine import FaqEngine

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("tg")


def send_message(chat_id: int, text: str) -> None:
    try:
        requests.post(f"{API}/sendMessage",
                      json={"chat_id": chat_id, "text": text}, timeout=15)
    except requests.RequestException as e:
        log.error("sendMessage error: %s", e)


def main() -> None:
    if not TOKEN:
        raise SystemExit("Не задан TELEGRAM_BOT_TOKEN в autoresponder/.env")

    engine = FaqEngine()
    log.info("Telegram авто-ответчик запущен. Правил: %d", len(engine.rules))

    offset = None
    while True:
        try:
            resp = requests.get(
                f"{API}/getUpdates",
                params={"timeout": 30, "offset": offset},
                timeout=40,
            )
            data = resp.json()
        except requests.RequestException as e:
            log.error("getUpdates error: %s", e)
            time.sleep(3)
            continue

        for upd in data.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message") or upd.get("edited_message")
            if not msg or "text" not in msg:
                continue
            chat_id = msg["chat"]["id"]
            text = msg["text"]
            answer = engine.reply(text)
            log.info("от %s: %r -> ответ %d симв.", chat_id, text[:40], len(answer))
            send_message(chat_id, answer)


if __name__ == "__main__":
    main()
