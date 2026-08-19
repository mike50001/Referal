"""Обработчики бота STU GO TRAVEL."""

from telegram.ext import Application

from . import cars, docs, license, photoid, sections, start, visas


def register_all(app: Application) -> None:
    """Зарегистрировать все обработчики."""
    start.register(app)
    cars.register(app)      # callback-кнопки списка авто
    visas.register(app)     # callback-кнопки типов виз
    docs.register(app)      # callback «Подробнее» в документах
    license.register(app)   # callback «Как получить тайские права»
    photoid.register(app)   # /photoid — получить код фото
    sections.register(app)  # обработчик кнопок-разделов — последним
