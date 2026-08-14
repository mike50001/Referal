"""Обработчики бота STU GO TRAVEL."""

from telegram.ext import Application

from . import cars, sections, start


def register_all(app: Application) -> None:
    """Зарегистрировать все обработчики."""
    start.register(app)
    cars.register(app)      # callback-кнопки списка авто
    sections.register(app)  # обработчик кнопок-разделов — последним
