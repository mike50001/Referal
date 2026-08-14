"""Команда /country — справка о стране."""

from __future__ import annotations

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes

from ..services.country import get_country
from ..services.http import ServiceError

_DRIVES = {"left": "левостороннее", "right": "правостороннее"}


def _format_number(n: float) -> str:
    return f"{n:,.0f}".replace(",", " ")


async def country(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = " ".join(context.args).strip()
    if not name:
        await update.message.reply_html(
            "Укажите страну: <code>/country Япония</code>"
        )
        return

    await update.effective_chat.send_action(ChatAction.TYPING)

    try:
        c = await get_country(name)
    except ServiceError as exc:
        await update.message.reply_text(f"⚠️ {exc}")
        return

    lines = [f"{c.flag} <b>{c.name}</b>"]
    if c.official_name and c.official_name != c.name:
        lines.append(f"<i>{c.official_name}</i>")
    lines.append("")
    lines.append(f"🏛 Столица: {c.capital}")

    region = c.region
    if c.subregion:
        region += f" ({c.subregion})"
    lines.append(f"🗺 Регион: {region}")
    lines.append(f"👥 Население: {_format_number(c.population)} чел.")
    if c.area:
        lines.append(f"📐 Площадь: {_format_number(c.area)} км²")
    if c.languages:
        lines.append(f"🗣 Языки: {', '.join(c.languages)}")
    if c.currencies:
        lines.append(f"💰 Валюта: {', '.join(c.currencies)}")
    if c.phone_code:
        lines.append(f"📞 Телефонный код: {c.phone_code}")
    if c.drives_on:
        lines.append(f"🚗 Движение: {_DRIVES.get(c.drives_on, c.drives_on)}")
    if c.timezones:
        tz = ", ".join(c.timezones[:4])
        if len(c.timezones) > 4:
            tz += f" и ещё {len(c.timezones) - 4}"
        lines.append(f"🕐 Часовые пояса: {tz}")
    if c.maps_url:
        lines.append(f"\n📍 <a href=\"{c.maps_url}\">Открыть на карте</a>")

    await update.message.reply_html("\n".join(lines), disable_web_page_preview=True)


def register(app: Application) -> None:
    app.add_handler(CommandHandler("country", country))
