"""Подменю «Визы»: типы виз и их описания (inline-кнопки)."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from ..content import GREEN_CORRIDOR, SECTIONS, VISAS, get_visa, tg_link
from ._util import go_home

PREFIX = "visa:"

_MENU_TEXT = "🏠 Главное меню — выбери раздел на клавиатуре ниже 👇"


def list_keyboard() -> InlineKeyboardMarkup:
    """Кнопки типов виз (по две в ряд) + «В меню»."""
    rows = [
        [InlineKeyboardButton(v["name"], callback_data=f"{PREFIX}v:{v['id']}")]
        for v in VISAS
    ]
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
    # info_only-визы (например, TR) — чисто информативные, без заявки.
    if not visa.get("info_only"):
        name = visa["name"].split(maxsplit=1)[-1]  # без ведущего эмодзи
        msg = (
            "Здравствуйте! Пишу из бота Stu Go Travel — интересует виза: "
            f"{name}"
        )
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
        await go_home(update, context)
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
        pages = visa.get("pages")
        if pages:
            # Длинный гайд — отправляем несколькими сообщениями,
            # клавиатуру вешаем на последнее.
            chat_id = query.message.chat_id
            for i, page in enumerate(pages):
                last = i == len(pages) - 1
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=page,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=_visa_keyboard(visa) if last else None,
                )
        else:
            await query.edit_message_text(
                visa["details"],
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=_visa_keyboard(visa),
            )


def register(app: Application) -> None:
    app.add_handler(CallbackQueryHandler(on_callback, pattern=f"^{PREFIX}"))
