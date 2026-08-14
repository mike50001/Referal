"""Обработчики команд Telegram-бота."""

from telegram.ext import Application

from . import checklist, common, country, currency, phrases, time, weather


def register_all(app: Application) -> None:
    """Зарегистрировать все обработчики в приложении."""
    common.register(app)
    weather.register(app)
    currency.register(app)
    country.register(app)
    time.register(app)
    phrases.register(app)
    checklist.register(app)
