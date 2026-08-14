"""Команды /start и /help, обработчик ошибок."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)

WELCOME = (
    "👋 <b>Привет, {name}!</b>\n\n"
    "Я — бот-помощник путешественника. Помогу с погодой, валютами, "
    "информацией о странах и не только.\n\n"
    "Напишите /help, чтобы увидеть все команды."
)

HELP = (
    "<b>🧭 Что я умею</b>\n\n"
    "🌦 <b>/weather</b> <i>город</i> — погода сейчас\n"
    "   <code>/weather Париж</code>\n\n"
    "💱 <b>/currency</b> <i>сумма из в</i> — конвертация валют\n"
    "   <code>/currency 100 USD RUB</code>\n\n"
    "🌍 <b>/country</b> <i>страна</i> — справка о стране\n"
    "   <code>/country Япония</code>\n\n"
    "🕐 <b>/time</b> <i>город</i> — местное время\n"
    "   <code>/time Токио</code>\n\n"
    "🗣 <b>/phrases</b> — разговорник базовых фраз\n\n"
    "🎒 <b>/checklist</b> — чек-листы для сборов\n\n"
    "❓ <b>/help</b> — эта справка"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    name = user.first_name if user else "путешественник"
    await update.message.reply_html(WELCOME.format(name=name))
    await update.message.reply_html(HELP)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(HELP)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Ошибка при обработке обновления:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Что-то пошло не так. Попробуйте ещё раз чуть позже."
        )


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Не знаю такой команды 🤔 Наберите /help, чтобы посмотреть список."
    )


def register(app: Application) -> None:
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_error_handler(on_error)
    # unknown регистрируется последним в main, чтобы не перехватывать команды.
