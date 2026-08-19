"""Обработчики бота STU GO TRAVEL."""

from telegram.ext import Application

from . import cars, docs, photoid, sections, start, visas


def register_all(app: Application) -> None:
    """Зарегистрировать все обработчики."""
    start.register(app)
    cars.register(app)      # callback-кнопки списка авто
    visas.register(app)     # callback-кнопки типов виз
    docs.register(app)      # callback «Подробнее» в документах
    photoid.register(app)   # /photoid — получить код фото
    sections.register(app)  # обработчик кнопок-разделов — последним
