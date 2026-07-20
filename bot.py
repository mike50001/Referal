"""Телеграм-бот «подруга», которая общается с тобой с помощью OpenAI.

Запуск:
    1. Установи зависимости:  pip install -r requirements.txt
    2. Создай файл .env (см. .env.example) с токенами.
    3. Запусти:  python bot.py
"""

import logging
import os
import random
import re
from collections import defaultdict, deque

from dotenv import load_dotenv
from openai import AsyncOpenAI, AuthenticationError, RateLimitError
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

# Убираем шум от фонового опроса Telegram, чтобы в логах были видны
# только важные сообщения и реальные ошибки (например, от OpenAI).
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

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

# --- Фотографии -----------------------------------------------------------

# Папка с картинками, которые бот может отправлять. Наполняешь её сам —
# кладёшь туда изображения, на которые у тебя есть права.
PHOTOS_DIR = os.getenv("PHOTOS_DIR", "photos")
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# Слова-триггеры: если сообщение просит фото — бот отправит картинку.
_PHOTO_REQUEST_RE = re.compile(
    r"\b(фото|фотк|фоточк|селфи|скинь.*(себя|фото)|покажи.*себя|пришли.*фото)",
    re.IGNORECASE,
)


def list_photos() -> list[str]:
    """Возвращает список путей к картинкам в папке PHOTOS_DIR."""
    if not os.path.isdir(PHOTOS_DIR):
        return []
    return [
        os.path.join(PHOTOS_DIR, name)
        for name in sorted(os.listdir(PHOTOS_DIR))
        if os.path.splitext(name)[1].lower() in _IMAGE_EXTS
    ]


def wants_photo(text: str) -> bool:
    """Похоже ли сообщение на просьбу прислать фото."""
    return bool(_PHOTO_REQUEST_RE.search(text or ""))


async def send_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет случайную картинку из папки или дерзко отказывает, если её нет."""
    photos = list_photos()
    if not photos:
        await update.message.reply_text(random.choice(personality.NO_PHOTOS_MESSAGES))
        return

    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
    with open(random.choice(photos), "rb") as img:
        await update.message.reply_photo(
            photo=img, caption=random.choice(personality.PHOTO_CAPTIONS)
        )


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
        "/photo — попросить фото (если заслужишь 💅)\n"
        "/help — эта подсказка"
    )


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Основной обработчик обычных текстовых сообщений."""
    chat_id = update.effective_chat.id
    user_text = update.message.text

    # Если просят фото — отправляем картинку из папки (или дерзко отказываем).
    if wants_photo(user_text):
        await send_photo(update, context)
        return

    # Показываем «печатает…», пока ждём ответ от OpenAI.
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        reply = await ask_openai(chat_id, user_text)
    except AuthenticationError:
        logger.error(
            "OpenAI: неверный ключ (AuthenticationError). Проверь переменную "
            "OPENAI_API_KEY — возможно, ключ отозван или скопирован с ошибкой."
        )
        reply = "Ой, у меня сейчас проблемы с доступом к «мозгу» 😔 Скоро починят!"
    except RateLimitError:
        logger.error(
            "OpenAI: превышен лимит / нет средств (RateLimitError, обычно "
            "insufficient_quota). Пополни баланс OpenAI в разделе Billing."
        )
        reply = "Ой, я немного устала думать 😔 Дай мне пару минут, попробуй позже."
    except Exception:
        logger.exception("OpenAI: непредвиденная ошибка при обращении к API")
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
    app.add_handler(CommandHandler("photo", send_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    logger.info("Бот %s запущен. Нажми Ctrl+C для остановки.", personality.BOT_NAME)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
