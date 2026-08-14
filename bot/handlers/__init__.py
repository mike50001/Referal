"""Обработчики бота STU GO TRAVEL."""

from telegram.ext import Application

from . import sections, start


def register_all(app: Application) -> None:
    """Зарегистрировать все обработчики."""
    start.register(app)
    sections.register(app)  # обработчик кнопок — последним
