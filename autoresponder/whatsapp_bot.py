"""WhatsApp FAQ-автоответчик через официальный Meta Cloud API (webhook).

WhatsApp присылает входящие сообщения на webhook (HTTP POST). Мы отвечаем
через Graph API. Нужен бизнес-аккаунт Meta и настройка (см. docs/autoresponder.md).

Переменные (autoresponder/.env):
  WHATSAPP_TOKEN         — постоянный/временный access token
  WHATSAPP_PHONE_ID      — Phone Number ID из панели Meta
  WHATSAPP_VERIFY_TOKEN  — произвольная строка, её же вписать в панели webhook
  WHATSAPP_PORT          — порт локального сервера (по умолчанию 8080)

Запуск:
    python whatsapp_bot.py
Важно: Meta требует HTTPS для webhook — перед этим сервисом нужен обратный
прокси с TLS (nginx/caddy) или туннель. Подробности в docs/autoresponder.md.
"""
from __future__ import annotations

import logging
import os

import requests
from dotenv import load_dotenv
from flask import Flask, request

from faq_engine import FaqEngine

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

TOKEN = os.getenv("WHATSAPP_TOKEN", "")
PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
PORT = int(os.getenv("WHATSAPP_PORT", "8080"))
GRAPH = f"https://graph.facebook.com/v20.0/{PHONE_ID}/messages"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("wa")

app = Flask(__name__)
engine = FaqEngine()


def send_message(to: str, text: str) -> None:
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    headers = {"Authorization": f"Bearer {TOKEN}"}
    try:
        r = requests.post(GRAPH, json=payload, headers=headers, timeout=15)
        if r.status_code >= 400:
            log.error("send error %s: %s", r.status_code, r.text[:200])
    except requests.RequestException as e:
        log.error("send exception: %s", e)


@app.get("/webhook")
def verify():
    # Подтверждение webhook при настройке в панели Meta.
    if (request.args.get("hub.mode") == "subscribe"
            and request.args.get("hub.verify_token") == VERIFY_TOKEN):
        return request.args.get("hub.challenge", ""), 200
    return "forbidden", 403


@app.post("/webhook")
def incoming():
    data = request.get_json(silent=True) or {}
    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    if msg.get("type") != "text":
                        continue
                    frm = msg["from"]
                    text = msg["text"]["body"]
                    answer = engine.reply(text)
                    log.info("от %s: %r", frm, text[:40])
                    send_message(frm, answer)
    except Exception as e:  # noqa: BLE001 — webhook не должен падать
        log.exception("webhook error: %s", e)
    return "ok", 200


if __name__ == "__main__":
    if not (TOKEN and PHONE_ID and VERIFY_TOKEN):
        raise SystemExit("Заполните WHATSAPP_* в autoresponder/.env")
    log.info("WhatsApp webhook на порту %d, правил: %d", PORT, len(engine.rules))
    app.run(host="0.0.0.0", port=PORT)
