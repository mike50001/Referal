"""Обработчики бота STU GO TRAVEL."""

from telegram.ext import Application

from . import cars, photoid, sections, start


def register_all(app: Application) -> None:
    """Зарегистрировать все обработчики."""
    start.register(app)
    cars.register(app)      # callback-кнопки списка авто
    photoid.register(app)   # /photoid — получить код фото
    sections.register(app)  # обработчик кнопок-разделов — последним
