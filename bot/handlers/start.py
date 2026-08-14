"""Команда /start: приветствие и показ главного меню."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ..content import PROMPT, WELCOME
from ..keyboards import main_menu


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Первое сообщение — приветствие.
    await update.message.reply_text(WELCOME)
    # Второе — с постоянной клавиатурой-меню.
    await update.message.reply_text(PROMPT, reply_markup=main_menu())


def register(app: Application) -> None:
    app.add_handler(CommandHandler("start", start))
    # /menu — быстро вернуть клавиатуру, если пользователь её скрыл.
    app.add_handler(CommandHandler("menu", start))
