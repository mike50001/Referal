"""Точка входа Telegram-бота обмена валюты."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat

from bot import rates
from bot.config import Config, load_config
from bot.handlers import admin_router, client_router
from bot.webapp import start_webapp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("exchange-bot")


async def set_commands(bot: Bot, config: Config) -> None:
    # Команды для всех пользователей.
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Запустить бота"),
            BotCommand(command="exchange", description="Оставить заявку на обмен"),
            BotCommand(command="rate", description="Узнать курс"),
            BotCommand(command="cancel", description="Отменить текущую заявку"),
        ]
    )
    # Дополнительные команды только в чате заявок (для админа).
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="rates", description="Показать текущие курсы"),
                BotCommand(command="setrate", description="Изменить курсы"),
                BotCommand(command="rate", description="Узнать курс"),
                BotCommand(command="cancel", description="Отмена"),
            ],
            scope=BotCommandScopeChat(chat_id=config.admin_chat_id),
        )
    except Exception as exc:
        logger.warning("Не удалось задать команды для админ-чата: %s", exc)


async def main() -> None:
    config = load_config()
    rates.load()  # подгружаем сохранённые обменником курсы

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # client_router первым: он ловит команды и шаги заявки.
    # admin_router вторым: он ловит reply-ответы в чате заявок.
    dp.include_router(client_router)
    dp.include_router(admin_router)

    await set_commands(bot, config)
    await bot.delete_webhook(drop_pending_updates=True)

    me = await bot.get_me()
    logger.info("Бот @%s запущен. Заявки уходят в чат %s", me.username, config.admin_chat_id)

    # Веб-сервер Mini App (калькулятор) — в том же процессе.
    web_runner = await start_webapp()

    try:
        # config прокидывается во все хендлеры как именованный аргумент.
        await dp.start_polling(bot, config=config)
    finally:
        await web_runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
