"""Команда /time — местное время в городе."""

from __future__ import annotations

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes

from ..services.http import ServiceError
from ..services.localtime import get_local_time

_WEEKDAYS = [
    "понедельник", "вторник", "среда", "четверг",
    "пятница", "суббота", "воскресенье",
]


async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    city = " ".join(context.args).strip()
    if not city:
        await update.message.reply_html(
            "Укажите город: <code>/time Токио</code>"
        )
        return

    await update.effective_chat.send_action(ChatAction.TYPING)

    try:
        lt = await get_local_time(city)
    except ServiceError as exc:
        await update.message.reply_text(f"⚠️ {exc}")
        return

    weekday = _WEEKDAYS[lt.now.weekday()]
    text = (
        f"🕐 <b>{lt.place.display}</b>\n\n"
        f"<b>{lt.now:%H:%M}</b>, {weekday}, {lt.now:%d.%m.%Y}\n"
        f"🌐 Часовой пояс: {lt.place.timezone} ({lt.utc_offset})"
    )
    await update.message.reply_html(text)


def register(app: Application) -> None:
    app.add_handler(CommandHandler("time", time_command))
