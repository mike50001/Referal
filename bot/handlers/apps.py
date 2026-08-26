"""Подменю «Полезные приложения»: категории и их списки (inline-кнопки)."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from ..content import APP_CATEGORIES, SECTIONS, get_app_category

PREFIX = "apps:"

_MENU_TEXT = "🏠 Главное меню — выбери раздел на клавиатуре ниже 👇"


def list_keyboard() -> InlineKeyboardMarkup:
    """Кнопки категорий (по две в ряд) + «В меню»."""
    btns = [
        InlineKeyboardButton(c["name"], callback_data=f"{PREFIX}c:{c['id']}")
        for c in APP_CATEGORIES
    ]
    rows = [btns[i : i + 2] for i in range(0, len(btns), 2)]
    rows.append([InlineKeyboardButton("🔙 В меню", callback_data=f"{PREFIX}menu")])
    return InlineKeyboardMarkup(rows)


def _cat_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                "🔙 К приложениям", callback_data=f"{PREFIX}list"
            )],
            [InlineKeyboardButton("🔙 В меню", callback_data=f"{PREFIX}menu")],
        ]
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data[len(PREFIX):]

    if data == "list":
        await query.edit_message_text(
            SECTIONS["apps"][1],
            parse_mode=ParseMode.HTML,
            reply_markup=list_keyboard(),
        )
    elif data == "menu":
        await query.edit_message_text(_MENU_TEXT, parse_mode=ParseMode.HTML)
    elif data.startswith("c:"):
        cat = get_app_category(data[2:])
        if cat is None:
            await query.edit_message_text(
                "Категория не найдена.", reply_markup=list_keyboard()
            )
            return
        await query.edit_message_text(
            cat["details"],
            parse_mode=ParseMode.HTML,
            reply_markup=_cat_keyboard(),
        )


def register(app: Application) -> None:
    app.add_handler(CallbackQueryHandler(on_callback, pattern=f"^{PREFIX}"))
