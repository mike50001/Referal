"""Точка входа: сборка и запуск бота STU GO TRAVEL."""

from __future__ import annotations

import logging

from telegram import BotCommand, Update
from telegram.ext import Application, ApplicationBuilder, ContextTypes

from .config import Config
from .content import DESCRIPTION, SHORT_DESCRIPTION
from .handlers import register_all

logger = logging.getLogger(__name__)

_COMMANDS = [
    BotCommand("start", "Запустить бота и открыть меню"),
    BotCommand("menu", "Показать меню разделов"),
]


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        level=getattr(logging, level, logging.INFO),
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Ошибка при обработке обновления:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Что-то пошло не так. Попробуйте ещё раз или наберите /start."
        )


async def _post_init(app: Application) -> None:
    await app.bot.set_my_commands(_COMMANDS)
    # Описание для экрана «Что умеет этот бот?» (видно до старта и после
    # удаления переписки) и короткое описание в профиле.
    try:
        await app.bot.set_my_description(DESCRIPTION)
        await app.bot.set_my_short_description(SHORT_DESCRIPTION)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не удалось обновить описание бота: %s", exc)
    me = await app.bot.get_me()
    logger.info("Бот @%s запущен.", me.username)


def build_application(config: Config) -> Application:
    app = (
        ApplicationBuilder()
        .token(config.bot_token)
        .post_init(_post_init)
        .build()
    )
    register_all(app)
    app.add_error_handler(_on_error)
    return app


def main() -> None:
    config = Config.from_env()
    _configure_logging(config.log_level)

    app = build_application(config)
    logger.info("Запуск в режиме long polling…")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
