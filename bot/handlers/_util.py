"""Общие помощники для обработчиков: кнопка и возврат в главное меню."""

from __future__ import annotations

from telegram import InlineKeyboardButton, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from ..content import PROMPT
from ..keyboards import main_menu

HOME_CB = "home"


def home_button() -> InlineKeyboardButton:
    """Кнопка «В меню» для любого раздела."""
    return InlineKeyboardButton("🏠 В меню", callback_data=HOME_CB)


async def go_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Убрать inline-кнопки текущего сообщения и прислать главное меню."""
    query = update.callback_query
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass
    await context.bot.send_message(
        chat_id=query.message.chat_id, text=PROMPT, reply_markup=main_menu()
    )


async def on_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    await go_home(update, context)


def register(app: Application) -> None:
    app.add_handler(CallbackQueryHandler(on_home, pattern=f"^{HOME_CB}$"))
