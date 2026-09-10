"""Общие помощники для обработчиков подменю."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ..content import PROMPT
from ..keyboards import main_menu


async def go_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Вернуть пользователя в главное меню: убрать inline-кнопки текущего
    сообщения и прислать меню с постоянной клавиатурой."""
    query = update.callback_query
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass
    await context.bot.send_message(
        chat_id=query.message.chat_id, text=PROMPT, reply_markup=main_menu()
    )
