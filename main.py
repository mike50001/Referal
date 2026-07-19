"""Точка входа Telegram-бота обмена валюты."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot.config import load_config
from bot.handlers import admin_router, client_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("exchange-bot")


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Запустить бота"),
            BotCommand(command="exchange", description="Оставить заявку на обмен"),
            BotCommand(command="rate", description="Узнать курс"),
            BotCommand(command="cancel", description="Отменить текущую заявку"),
        ]
    )


async def main() -> None:
    config = load_config()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # client_router первым: он ловит команды и шаги заявки.
    # admin_router вторым: он ловит reply-ответы в чате заявок.
    dp.include_router(client_router)
    dp.include_router(admin_router)

    await set_commands(bot)
    await bot.delete_webhook(drop_pending_updates=True)

    me = await bot.get_me()
    logger.info("Бот @%s запущен. Заявки уходят в чат %s", me.username, config.admin_chat_id)

    # config прокидывается во все хендлеры как именованный аргумент.
    await dp.start_polling(bot, config=config)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
