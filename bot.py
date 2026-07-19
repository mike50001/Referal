"""Телеграм-бот «подруга», которая общается с тобой с помощью OpenAI.

Запуск:
    1. Установи зависимости:  pip install -r requirements.txt
    2. Создай файл .env (см. .env.example) с токенами.
    3. Запусти:  python bot.py
"""

import logging
import os
from collections import defaultdict, deque

from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import personality

# --- Загрузка настроек из окружения ---------------------------------------

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Модель можно поменять в .env; по умолчанию — недорогая и умная.
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
# Сколько последних сообщений помнить в разговоре (пар «ты — она»).
HISTORY_LIMIT = int(os.getenv("HISTORY_LIMIT", "20"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- Клиент OpenAI и память диалогов --------------------------------------

# Клиент создаётся лениво (только когда реально нужен), чтобы при отсутствии
# ключа бот показывал понятную ошибку в main(), а не падал при импорте.
_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _client


# История для каждого пользователя: chat_id -> очередь сообщений.
# Храним в памяти процесса; при перезапуске бота история очищается.
histories: dict[int, deque] = defaultdict(lambda: deque(maxlen=HISTORY_LIMIT * 2))


async def ask_openai(chat_id: int, user_text: str) -> str:
    """Отправляет сообщение пользователя в OpenAI с учётом истории и характера."""
    history = histories[chat_id]
    history.append({"role": "user", "content": user_text})

    messages = [{"role": "system", "content": personality.SYSTEM_PROMPT}]
    messages.extend(history)

    response = await get_client().chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.9,
        max_tokens=500,
    )
    reply = (response.choices[0].message.content or "").strip()

    history.append({"role": "assistant", "content": reply})
    return reply


# --- Обработчики команд и сообщений ---------------------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start — знакомство."""
    histories.pop(update.effective_chat.id, None)
    await update.message.reply_text(personality.GREETING)


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /reset — очистить память разговора."""
    histories.pop(update.effective_chat.id, None)
    await update.message.reply_text(personality.RESET_MESSAGE)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /help — список возможностей."""
    await update.message.reply_text(
        f"Я {personality.BOT_NAME} — просто пиши мне что угодно, и я отвечу 🙂\n\n"
        "Команды:\n"
        "/start — начать заново и познакомиться\n"
        "/reset — забыть наш прошлый разговор\n"
        "/help — эта подсказка"
    )


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Основной обработчик обычных текстовых сообщений."""
    chat_id = update.effective_chat.id
    user_text = update.message.text

    # Показываем «печатает…», пока ждём ответ от OpenAI.
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        reply = await ask_openai(chat_id, user_text)
    except Exception:
        logger.exception("Ошибка при обращении к OpenAI")
        reply = (
            "Ой, что-то у меня сейчас не получается ответить 😔 "
            "Попробуй, пожалуйста, ещё раз через минутку."
        )

    await update.message.reply_text(reply)


# --- Точка входа -----------------------------------------------------------


def main() -> None:
    if not TELEGRAM_TOKEN:
        raise RuntimeError(
            "Не задан TELEGRAM_BOT_TOKEN. Создай файл .env по образцу .env.example."
        )
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "Не задан OPENAI_API_KEY. Создай файл .env по образцу .env.example."
        )

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    logger.info("Бот %s запущен. Нажми Ctrl+C для остановки.", personality.BOT_NAME)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
