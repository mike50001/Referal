"""Точка входа: сборка и запуск Telegram-бота путешественника."""

from __future__ import annotations

import logging

from telegram import BotCommand
from telegram.ext import Application, ApplicationBuilder, MessageHandler, filters

from .config import Config
from .handlers import register_all
from .handlers.common import unknown
from .services.http import close_client

logger = logging.getLogger(__name__)

_COMMANDS = [
    BotCommand("start", "Запустить бота"),
    BotCommand("weather", "Погода в городе"),
    BotCommand("currency", "Конвертация валют"),
    BotCommand("country", "Информация о стране"),
    BotCommand("time", "Местное время в городе"),
    BotCommand("phrases", "Разговорник"),
    BotCommand("checklist", "Чек-листы для сборов"),
    BotCommand("help", "Помощь"),
]


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        level=getattr(logging, level, logging.INFO),
    )
    # Библиотека httpx слишком многословна на уровне INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def _post_init(app: Application) -> None:
    await app.bot.set_my_commands(_COMMANDS)
    me = await app.bot.get_me()
    logger.info("Бот @%s запущен.", me.username)


async def _post_shutdown(app: Application) -> None:
    await close_client()
    logger.info("Бот остановлен, соединения закрыты.")


def build_application(config: Config) -> Application:
    app = (
        ApplicationBuilder()
        .token(config.bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    register_all(app)
    # Обработчик неизвестных команд регистрируется последним.
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    return app


def main() -> None:
    config = Config.from_env()
    _configure_logging(config.log_level)

    app = build_application(config)
    logger.info("Запуск в режиме long polling…")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
