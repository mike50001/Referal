"""Обработчик нажатий на кнопки меню (текстовые сообщения)."""

from __future__ import annotations

import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from ..content import (
    SECTION_BUTTONS,
    SECTION_PHOTOS,
    SECTIONS,
    find_key_by_label,
)
from ..keyboards import main_menu

logger = logging.getLogger(__name__)
from .cars import entry_button as cars_entry_button
from .docs import entry_button as docs_entry_button
from .visas import list_keyboard as visas_list_keyboard

_FALLBACK = (
    "Не понял запрос 🤔\n"
    "Выбери раздел на клавиатуре ниже или набери /start."
)


def _inline_for(key: str) -> InlineKeyboardMarkup | None:
    """Собрать inline-клавиатуру со ссылками для раздела, если заданы."""
    buttons = SECTION_BUTTONS.get(key)
    if not buttons:
        return None
    rows = [[InlineKeyboardButton(text, url=url)] for text, url in buttons]
    return InlineKeyboardMarkup(rows)


async def _send_section_photos(update: Update, context, key: str) -> None:
    """Отправить фото раздела (если заданы) перед текстом."""
    photos = SECTION_PHOTOS.get(key)
    if not photos:
        return
    chat_id = update.effective_chat.id
    try:
        if len(photos) == 1:
            await context.bot.send_photo(chat_id, photos[0])
        else:
            media = [InputMediaPhoto(p) for p in photos[:10]]
            await context.bot.send_media_group(chat_id, media)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не удалось отправить фото раздела %s: %s", key, exc)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    key = find_key_by_label(text)
    if key is None:
        await update.message.reply_text(_FALLBACK, reply_markup=main_menu())
        return

    body = SECTIONS[key][1]

    # Раздел «Документы» — краткие тезисы + кнопка «Подробнее».
    if key == "docs":
        await update.message.reply_text(
            body,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=docs_entry_button(),
        )
        return

    # Раздел «Аренда авто» открывает подменю со списком машин.
    if key == "car":
        await update.message.reply_text(
            body,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=cars_entry_button(),
        )
        return

    # Раздел «Визы» показывает интро + инлайн-кнопки типов виз.
    if key == "visa":
        await update.message.reply_text(
            body,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=visas_list_keyboard(),
        )
        return

    # Фото раздела (если заданы) — перед текстом.
    await _send_section_photos(update, context, key)

    inline = _inline_for(key)
    # Reply-клавиатура постоянная (is_persistent) и остаётся на экране,
    # поэтому для разделов со ссылкой прикрепляем inline-кнопки.
    if inline is not None:
        await update.message.reply_text(
            body,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=inline,
        )
    else:
        await update.message.reply_text(
            body,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=main_menu(),
        )


def register(app: Application) -> None:
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, on_message)
    )
