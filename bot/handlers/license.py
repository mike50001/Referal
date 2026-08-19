"""Раздел «Водительские права»: кнопка «Как получить тайские права»."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from ..content import LICENSE_THAI, SECTIONS

PREFIX = "lic:"

_MENU_TEXT = "🏠 Главное меню — выбери раздел на клавиатуре ниже 👇"
_REQUEST_CONTACT = "https://t.me/Stu_Art_x"


def entry_button() -> InlineKeyboardMarkup:
    """Кнопка под основным текстом раздела прав."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            "🪪 Как получить тайские права", callback_data=f"{PREFIX}thai"
        )]]
    )


def _thai_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📝 Оставить заявку", url=_REQUEST_CONTACT)],
            [InlineKeyboardButton("🔙 Назад", callback_data=f"{PREFIX}back")],
            [InlineKeyboardButton("🔙 В меню", callback_data=f"{PREFIX}menu")],
        ]
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data[len(PREFIX):]

    if data == "thai":
        await query.edit_message_text(
            LICENSE_THAI,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=_thai_keyboard(),
        )
    elif data == "back":
        await query.edit_message_text(
            SECTIONS["license"][1],
            parse_mode=ParseMode.HTML,
            reply_markup=entry_button(),
        )
    elif data == "menu":
        await query.edit_message_text(_MENU_TEXT, parse_mode=ParseMode.HTML)


def register(app: Application) -> None:
    app.add_handler(CallbackQueryHandler(on_callback, pattern=f"^{PREFIX}"))
