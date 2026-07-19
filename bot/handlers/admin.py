"""Хендлеры админ-части: ответ клиенту reply-сообщением на заявку.

Роутинг ответа полностью бесстостоянийный: ID клиента зашит в текст
заявки (маркер CLIENT_ID_MARKER), поэтому ответы работают даже после
перезапуска бота — без базы данных.
"""
from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot import rates
from bot.config import Config
from bot.handlers.client import CLIENT_ID_MARKER

router = Router(name="admin")

_CLIENT_ID_RE = re.compile(re.escape(CLIENT_ID_MARKER) + r"\s*(\d+)")


def _extract_client_id(text: str | None) -> int | None:
    if not text:
        return None
    match = _CLIENT_ID_RE.search(text)
    return int(match.group(1)) if match else None


@router.message(Command("rates"))
async def show_rates(message: Message, config: Config) -> None:
    """Диагностика: показать текущие курсы. Только в чате заявок."""
    if message.chat.id != config.admin_chat_id:
        return
    text = await rates.snapshot_text()
    if config.markup_percent:
        text += f"\n\nНаценка обменника: {config.markup_percent:g}%"
    await message.answer(text)


@router.message(F.reply_to_message)
async def reply_to_client(message: Message, config: Config) -> None:
    # Реагируем только на ответы, отправленные в чат заявок.
    if message.chat.id != config.admin_chat_id:
        return

    client_id = _extract_client_id(message.reply_to_message.text)
    if client_id is None:
        # Реплай не на сообщение-заявку — игнорируем.
        return

    if not config.is_admin(message.from_user.id):
        await message.reply("У вас нет прав отвечать клиентам.")
        return

    answer = message.text or message.caption
    if not answer:
        await message.reply("Ответ клиенту можно отправить только текстом.")
        return

    try:
        await message.bot.send_message(
            client_id,
            f"💬 <b>Ответ менеджера:</b>\n\n{answer}",
        )
    except Exception:
        await message.reply(
            "⚠️ Не удалось доставить ответ клиенту "
            "(возможно, он остановил бота)."
        )
        return

    await message.reply("✅ Ответ отправлен клиенту.")
