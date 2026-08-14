"""Команда /currency — конвертация валют."""

from __future__ import annotations

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes

from ..services.currency import convert
from ..services.http import ServiceError

_USAGE = (
    "Формат: <code>/currency сумма ИЗ В</code>\n"
    "Например: <code>/currency 100 USD RUB</code>"
)


def _parse_amount(raw: str) -> float:
    return float(raw.replace(",", ".").replace(" ", ""))


async def currency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 3:
        await update.message.reply_html(_USAGE)
        return

    try:
        amount = _parse_amount(args[0])
    except ValueError:
        await update.message.reply_html(
            "Первым аргументом должна быть сумма.\n\n" + _USAGE
        )
        return

    if amount <= 0:
        await update.message.reply_text("Сумма должна быть больше нуля.")
        return

    from_cur, to_cur = args[1], args[2]

    await update.effective_chat.send_action(ChatAction.TYPING)

    try:
        c = await convert(amount, from_cur, to_cur)
    except ServiceError as exc:
        await update.message.reply_text(f"⚠️ {exc}")
        return

    rate_line = ""
    if c.date != "—":
        rate_line = (
            f"\n\n📊 Курс: 1 {c.from_currency} = {c.rate:.4f} {c.to_currency}"
            f"\n🗓 На дату: {c.date}"
        )

    text = (
        f"💱 <b>{c.amount:g} {c.from_currency}</b> = "
        f"<b>{c.result:,.2f} {c.to_currency}</b>".replace(",", " ")
        + rate_line
    )
    await update.message.reply_html(text)


def register(app: Application) -> None:
    app.add_handler(CommandHandler("currency", currency))
