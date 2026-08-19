"""Раздел «Документы»: краткие тезисы + кнопка «Подробнее» с полным списком."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from ..content import DOCS_FULL, SECTIONS

PREFIX = "docs:"

_MENU_TEXT = "🏠 Главное меню — выбери раздел на клавиатуре ниже 👇"


def entry_button() -> InlineKeyboardMarkup:
    """Кнопка «Подробнее» под кратким текстом раздела."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("📖 Подробнее", callback_data=f"{PREFIX}full")]]
    )


def _full_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔙 Кратко", callback_data=f"{PREFIX}short")],
            [InlineKeyboardButton("🔙 В меню", callback_data=f"{PREFIX}menu")],
        ]
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data[len(PREFIX):]

    if data == "full":
        await query.edit_message_text(
            DOCS_FULL,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=_full_keyboard(),
        )
    elif data == "short":
        await query.edit_message_text(
            SECTIONS["docs"][1],
            parse_mode=ParseMode.HTML,
            reply_markup=entry_button(),
        )
    elif data == "menu":
        await query.edit_message_text(_MENU_TEXT, parse_mode=ParseMode.HTML)


def register(app: Application) -> None:
    app.add_handler(CallbackQueryHandler(on_callback, pattern=f"^{PREFIX}"))
