"""Обработчик нажатий на кнопки меню (текстовые сообщения)."""

from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from ..content import find_section_by_label
from ..keyboards import main_menu

_FALLBACK = (
    "Не понял запрос 🤔\n"
    "Выбери раздел на клавиатуре ниже или набери /start."
)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    body = find_section_by_label(text)
    if body is None:
        await update.message.reply_text(_FALLBACK, reply_markup=main_menu())
        return
    await update.message.reply_text(
        body,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=main_menu(),
    )


def register(app: Application) -> None:
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, on_message)
    )
