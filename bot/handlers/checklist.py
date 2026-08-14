"""Команда /checklist — чек-листы для сборов с выбором категории."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from ..services.checklist import get_checklist, list_categories

_PREFIX = "checklist:"


def _keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(title, callback_data=f"{_PREFIX}{key}")
        for key, title in list_categories()
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


def _render(key: str) -> str:
    item = get_checklist(key)
    if not item:
        return "Список не найден."
    title, items = item
    lines = [f"<b>{title}</b>\n"]
    lines.extend(f"☑️ {i}" for i in items)
    return "\n".join(lines)


async def checklist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(
        "🎒 <b>Чек-листы для сборов</b>\nВыберите категорию:",
        reply_markup=_keyboard(),
    )


async def on_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    key = query.data[len(_PREFIX):]
    await query.edit_message_text(
        _render(key),
        parse_mode="HTML",
        reply_markup=_keyboard(),
    )


def register(app: Application) -> None:
    app.add_handler(CommandHandler("checklist", checklist))
    app.add_handler(CallbackQueryHandler(on_category, pattern=f"^{_PREFIX}"))
