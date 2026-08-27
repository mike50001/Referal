"""Команда /start: баннер, приветствие и показ главного меню."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ..content import PROMPT, START_BANNER, WELCOME
from ..keyboards import main_menu

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Баннер с приветствием-подписью (если задан), иначе просто текст.
    if START_BANNER:
        try:
            await update.message.reply_photo(START_BANNER, caption=WELCOME)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось отправить баннер: %s", exc)
            await update.message.reply_text(WELCOME)
    else:
        await update.message.reply_text(WELCOME)
    # Сообщение с постоянной клавиатурой-меню.
    await update.message.reply_text(PROMPT, reply_markup=main_menu())


def register(app: Application) -> None:
    app.add_handler(CommandHandler("start", start))
    # /menu — быстро вернуть клавиатуру, если пользователь её скрыл.
    app.add_handler(CommandHandler("menu", start))
