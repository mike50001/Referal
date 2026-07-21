"""Точка входа Telegram-бота обмена валюты."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat

from bot import keyboards, rates
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


# Текст на стартовом экране бота (виден в пустом чате до нажатия «Запустить»).
BOT_DESCRIPTION = (
    "💱 Обменник Misha Cash — быстрый и безопасный обмен валют: "
    "рубль, тенге, бат, USDT.\n\n"
    "⚡ Быстро   💵 Выгодный курс   🔒 Надёжно\n\n"
    "Нажмите «Запустить», чтобы узнать актуальный курс, открыть калькулятор "
    "и оставить заявку.\n\n"
    "⚠️ Остерегайтесь мошенников — общайтесь только здесь."
)

# Короткое описание в профиле бота.
BOT_SHORT_DESCRIPTION = (
    "💱 Misha Cash — обмен валют: рубль, тенге, бат, USDT. Быстро и надёжно."
)


async def set_profile(bot: Bot) -> None:
    try:
        await bot.set_my_description(description=BOT_DESCRIPTION)
        await bot.set_my_short_description(short_description=BOT_SHORT_DESCRIPTION)
    except Exception as exc:
        logger.warning("Не удалось задать описание бота: %s", exc)


async def main() -> None:
    config = load_config()
    rates.load()  # подгружаем сохранённые обменником курсы
    keyboards.set_webapp_url(config.webapp_url)  # кнопка Mini App, если задан URL

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
    await set_profile(bot)
    await bot.delete_webhook(drop_pending_updates=True)

    me = await bot.get_me()
    logger.info("Бот @%s запущен. Заявки уходят в чат %s", me.username, config.admin_chat_id)

    # Веб-сервер Mini App (калькулятор) — в том же процессе.
    web_runner = await start_webapp(bot, config)

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
