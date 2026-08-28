"""Подменю «Визы»: типы виз и их описания (inline-кнопки)."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from ..content import GREEN_CORRIDOR, SECTIONS, VISAS, get_visa, tg_link

PREFIX = "visa:"

_MENU_TEXT = "🏠 Главное меню — выбери раздел на клавиатуре ниже 👇"


def list_keyboard() -> InlineKeyboardMarkup:
    """Кнопки типов виз (по две в ряд) + «В меню»."""
    btns = [
        InlineKeyboardButton(v["name"], callback_data=f"{PREFIX}v:{v['id']}")
        for v in VISAS
    ]
    rows = [btns[i : i + 2] for i in range(0, len(btns), 2)]
    rows.append(
        [InlineKeyboardButton(
            "🟢 Зелёный коридор", callback_data=f"{PREFIX}green"
        )]
    )
    rows.append([InlineKeyboardButton("🔙 В меню", callback_data=f"{PREFIX}menu")])
    return InlineKeyboardMarkup(rows)


def _green_keyboard() -> InlineKeyboardMarkup:
    msg = "Здравствуйте! Пишу из бота Stu Go Travel — интересует зелёный коридор"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                "📝 Оставить заявку", url=tg_link("Stu_Art_x", msg)
            )],
            [InlineKeyboardButton("🔙 К видам виз", callback_data=f"{PREFIX}list")],
            [InlineKeyboardButton("🔙 В меню", callback_data=f"{PREFIX}menu")],
        ]
    )


def _visa_keyboard(visa: dict) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    # Кнопки-ссылки конкретной визы (если заданы отдельно).
    for label, url in visa.get("buttons") or []:
        rows.append([InlineKeyboardButton(label, url=url)])
    # Общая кнопка заявки под каждой визой -> @Stu_Art_x с готовым текстом.
    name = visa["name"].split(maxsplit=1)[-1]  # без ведущего эмодзи
    msg = f"Здравствуйте! Пишу из бота Stu Go Travel — интересует виза: {name}"
    rows.append(
        [InlineKeyboardButton(
            "📝 Оставить заявку", url=tg_link("Stu_Art_x", msg)
        )]
    )
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
    elif data == "green":
        await query.edit_message_text(
            GREEN_CORRIDOR,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=_green_keyboard(),
        )
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
