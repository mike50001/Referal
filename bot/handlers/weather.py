"""Команда /weather — текущая погода в городе."""

from __future__ import annotations

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes

from ..services.http import ServiceError
from ..services.weather import get_weather


async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    city = " ".join(context.args).strip()
    if not city:
        await update.message.reply_html(
            "Укажите город: <code>/weather Париж</code>"
        )
        return

    await update.effective_chat.send_action(ChatAction.TYPING)

    try:
        w = await get_weather(city)
    except ServiceError as exc:
        await update.message.reply_text(f"⚠️ {exc}")
        return

    text = (
        f"{w.emoji} <b>Погода: {w.place.display}</b>\n\n"
        f"{w.description}\n"
        f"🌡 Температура: <b>{w.temperature:.0f}°C</b> "
        f"(ощущается как {w.feels_like:.0f}°C)\n"
        f"📈 Сегодня: от {w.temp_min:.0f}°C до {w.temp_max:.0f}°C\n"
        f"💧 Влажность: {w.humidity}%\n"
        f"💨 Ветер: {w.wind_speed:.0f} км/ч"
    )
    await update.message.reply_html(text)


def register(app: Application) -> None:
    app.add_handler(CommandHandler("weather", weather))
