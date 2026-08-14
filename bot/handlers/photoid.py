"""Утилита /photoid: получить код (file_id) фото, отправив его боту.

Позволяет добавлять фото машин без загрузки файлов в репозиторий:
1. Отправь боту /photoid
2. Пришли фото (можно альбомом) — бот ответит кодом каждого
3. Перешли коды разработчику — они прописываются в CARS
"""

from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

_FLAG = "photoid_mode"


async def start_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[_FLAG] = True
    await update.message.reply_text(
        "📸 Режим получения кодов включён.\n\n"
        "Пришли фото (можно альбомом) — верну код (file_id) каждого. "
        "Скопируй коды и пришли их мне/разработчику.\n\n"
        "Выйти — /stopid"
    )


async def stop_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(_FLAG, None)
    await update.message.reply_text("Готово, режим выключен.")


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get(_FLAG):
        return
    # Берём самое большое разрешение.
    file_id = update.message.photo[-1].file_id
    await update.message.reply_text(
        f"<code>{file_id}</code>", parse_mode=ParseMode.HTML
    )


def register(app: Application) -> None:
    app.add_handler(CommandHandler("photoid", start_mode))
    app.add_handler(CommandHandler("stopid", stop_mode))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
