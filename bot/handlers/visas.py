"""Подменю «Визы»: типы виз и их описания (inline-кнопки)."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from ..content import SECTIONS, VISAS, get_visa

PREFIX = "visa:"

_MENU_TEXT = "🏠 Главное меню — выбери раздел на клавиатуре ниже 👇"


def list_keyboard() -> InlineKeyboardMarkup:
    """Кнопки типов виз (по две в ряд) + «В меню»."""
    btns = [
        InlineKeyboardButton(v["name"], callback_data=f"{PREFIX}v:{v['id']}")
        for v in VISAS
    ]
    rows = [btns[i : i + 2] for i in range(0, len(btns), 2)]
    rows.append([InlineKeyboardButton("🔙 В меню", callback_data=f"{PREFIX}menu")])
    return InlineKeyboardMarkup(rows)


def _visa_keyboard(visa: dict) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    # Кнопки-ссылки конкретной визы (заявки и т.п.), если заданы.
    for label, url in visa.get("buttons") or []:
        rows.append([InlineKeyboardButton(label, url=url)])
    rows.append(
        [InlineKeyboardButton("🔙 К видам виз", callback_data=f"{PREFIX}list")]
    )
    rows.append(
        [InlineKeyboardButton("🔙 В меню", callback_data=f"{PREFIX}menu")]
    )
    return InlineKeyboardMarkup(rows)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data[len(PREFIX):]

    if data == "list":
        await query.edit_message_text(
            SECTIONS["visa"][1],
            parse_mode=ParseMode.HTML,
            reply_markup=list_keyboard(),
        )
    elif data == "menu":
        await query.edit_message_text(_MENU_TEXT, parse_mode=ParseMode.HTML)
    elif data.startswith("v:"):
        visa = get_visa(data[2:])
        if visa is None:
            await query.edit_message_text(
                "Тип визы не найден.", reply_markup=list_keyboard()
            )
            return
        await query.edit_message_text(
            visa["details"],
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=_visa_keyboard(visa),
        )


def register(app: Application) -> None:
    app.add_handler(CallbackQueryHandler(on_callback, pattern=f"^{PREFIX}"))
