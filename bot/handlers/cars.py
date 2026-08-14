"""Подменю «Аренда авто»: список машин и карточки (inline-кнопки)."""

from __future__ import annotations

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from ..content import CARS, car_booking_url, car_photo_paths, get_car

PREFIX = "cars:"

_LIST_TITLE = "🚗 <b>Доступные авто</b>\nВыбери вариант 👇"
_MENU_TEXT = "🏠 Главное меню — выбери раздел на клавиатуре ниже 👇"


def entry_button() -> InlineKeyboardMarkup:
    """Кнопка под текстом раздела «Аренда авто»."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            "🚗 Посмотреть доступные авто", callback_data=f"{PREFIX}list"
        )]]
    )


def _list_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(car["name"], callback_data=f"{PREFIX}c:{car['id']}")]
        for car in CARS
    ]
    rows.append([InlineKeyboardButton("⬅️ В меню", callback_data=f"{PREFIX}menu")])
    return InlineKeyboardMarkup(rows)


def _car_keyboard(car: dict[str, str]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("🚗 К списку авто", callback_data=f"{PREFIX}list"),
            InlineKeyboardButton("⬅️ В меню", callback_data=f"{PREFIX}menu"),
        ],
    ]
    url = car_booking_url(car["name"])
    if url:
        rows.append(
            [InlineKeyboardButton("📩 Забронировать эту машину", url=url)]
        )
    return InlineKeyboardMarkup(rows)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data[len(PREFIX):]

    if data == "list":
        await query.edit_message_text(
            _LIST_TITLE, parse_mode=ParseMode.HTML, reply_markup=_list_keyboard()
        )
    elif data == "menu":
        await query.edit_message_text(_MENU_TEXT, parse_mode=ParseMode.HTML)
    elif data.startswith("c:"):
        car = get_car(data[2:])
        if car is None:
            await query.edit_message_text(
                "Машина не найдена.", reply_markup=_list_keyboard()
            )
            return

        photos = car_photo_paths(car["id"])
        if photos:
            # Есть фото: отправляем альбом + отдельным сообщением карточку.
            media = [
                InputMediaPhoto(p.read_bytes()) for p in photos[:10]
            ]
            await context.bot.send_media_group(
                chat_id=query.message.chat_id, media=media
            )
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=car["details"],
                parse_mode=ParseMode.HTML,
                reply_markup=_car_keyboard(car),
            )
        else:
            # Фото нет — просто показываем карточку на месте.
            await query.edit_message_text(
                car["details"],
                parse_mode=ParseMode.HTML,
                reply_markup=_car_keyboard(car),
            )


def register(app: Application) -> None:
    app.add_handler(CallbackQueryHandler(on_callback, pattern=f"^{PREFIX}"))
