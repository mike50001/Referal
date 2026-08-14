"""Команда /phrases — разговорник с выбором языка через кнопки."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from ..services.phrasebook import available_languages, phrases_for

_PREFIX = "phrases:"


def _language_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(name, callback_data=f"{_PREFIX}{code}")
        for code, name in available_languages()
    ]
    # По две кнопки в ряд.
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


def _render(code: str) -> str:
    data = phrases_for(code)
    if not data:
        return "Язык не найден."
    lines = [f"<b>{data['lang']}</b>\n"]
    for ru, translation in data.items():
        if ru == "lang":
            continue
        lines.append(f"• <b>{ru}</b> — {translation}")
    return "\n".join(lines)


async def phrases(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(
        "🗣 <b>Разговорник</b>\nВыберите язык:",
        reply_markup=_language_keyboard(),
    )


async def on_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    code = query.data[len(_PREFIX):]
    await query.edit_message_text(
        _render(code),
        parse_mode="HTML",
        reply_markup=_language_keyboard(),
    )


def register(app: Application) -> None:
    app.add_handler(CommandHandler("phrases", phrases))
    app.add_handler(CallbackQueryHandler(on_language, pattern=f"^{_PREFIX}"))
