"""Команды /start и /menu: баннер, гайд, приветствие и главное меню."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ..content import (
    GUIDE_CAPTION,
    GUIDE_FILE_ID,
    PROMPT,
    START_BANNER,
    WELCOME,
)
from ..keyboards import main_menu

logger = logging.getLogger(__name__)


async def _send_start(update: Update, with_guide: bool) -> None:
    # Баннер с приветствием-подписью (если задан), иначе просто текст.
    if START_BANNER:
        try:
            await update.message.reply_photo(START_BANNER, caption=WELCOME)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось отправить баннер: %s", exc)
            await update.message.reply_text(WELCOME)
    else:
        await update.message.reply_text(WELCOME)

    # PDF-гайд (только на /start).
    if with_guide and GUIDE_FILE_ID:
        try:
            await update.message.reply_document(
                GUIDE_FILE_ID, caption=GUIDE_CAPTION, parse_mode="HTML"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось отправить гайд: %s", exc)

    # Сообщение с постоянной клавиатурой-меню.
    await update.message.reply_text(PROMPT, reply_markup=main_menu())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_start(update, with_guide=True)


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_start(update, with_guide=False)


def register(app: Application) -> None:
    app.add_handler(CommandHandler("start", start))
    # /menu — быстро вернуть клавиатуру (без гайда).
    app.add_handler(CommandHandler("menu", menu))
