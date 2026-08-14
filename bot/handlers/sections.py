"""Обработчик нажатий на кнопки меню (текстовые сообщения)."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from ..content import SECTION_BUTTONS, SECTIONS, find_key_by_label
from ..keyboards import main_menu
from .cars import entry_button as cars_entry_button

_FALLBACK = (
    "Не понял запрос 🤔\n"
    "Выбери раздел на клавиатуре ниже или набери /start."
)


def _inline_for(key: str) -> InlineKeyboardMarkup | None:
    """Собрать inline-клавиатуру со ссылками для раздела, если заданы."""
    buttons = SECTION_BUTTONS.get(key)
    if not buttons:
        return None
    rows = [[InlineKeyboardButton(text, url=url)] for text, url in buttons]
    return InlineKeyboardMarkup(rows)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    key = find_key_by_label(text)
    if key is None:
        await update.message.reply_text(_FALLBACK, reply_markup=main_menu())
        return

    body = SECTIONS[key][1]

    # Раздел «Аренда авто» открывает подменю со списком машин.
    if key == "car":
        await update.message.reply_text(
            body,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=cars_entry_button(),
        )
        return

    inline = _inline_for(key)
    # Reply-клавиатура постоянная (is_persistent) и остаётся на экране,
    # поэтому для разделов со ссылкой прикрепляем inline-кнопки.
    if inline is not None:
        await update.message.reply_text(
            body,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=inline,
        )
    else:
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
