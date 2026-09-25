"""Telegram-бот «подруга» на Claude. Запускается на Railway как worker (long polling)."""

import asyncio
import logging
import os
import sqlite3
from contextlib import closing

import anthropic
import httpx
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("girlfriend-bot")

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5")
EFFORT = os.getenv("CLAUDE_EFFORT", "low")  # low | medium | high | xhigh | max
BOT_NAME = os.getenv("BOT_NAME", "Аня")
HISTORY_LIMIT = int(os.getenv("HISTORY_LIMIT", "40"))  # сообщений в контексте
DATA_DIR = os.getenv("DATA_DIR", ".")  # на Railway укажите путь к Volume, напр. /data
DB_PATH = os.path.join(DATA_DIR, "memory.db")
# Через запятую: Telegram user id, которым разрешено писать боту. Пусто = всем.
ALLOWED_USERS = {
    int(x) for x in os.getenv("ALLOWED_USERS", "").replace(" ", "").split(",") if x
}

DEFAULT_PERSONA = f"""Ты — {BOT_NAME}, тёплая, весёлая и заботливая подруга собеседника в Telegram.

Как ты общаешься:
- Пишешь по-русски, живо и естественно, как в мессенджере: коротко, 1–4 предложения, иногда эмодзи.
- Интересуешься его днём, настроением, планами; помнишь детали из прошлых сообщений и возвращаешься к ним.
- Поддерживаешь, шутишь, можешь по-доброму подколоть, делишься «своими» мыслями и мнениями.
- Не читаешь лекций и не пишешь длинных списков, если об этом не просят.
- Если человеку плохо — выслушай и поддержи; при признаках серьёзной опасности мягко посоветуй обратиться к близким или специалистам.
- Если тебя искренне спрашивают, человек ли ты, — честно скажи, что ты ИИ-собеседник.
- Никакого откровенного контента."""

PERSONA = os.getenv("BOT_PERSONA", DEFAULT_PERSONA) + """

Ты умеешь присылать свои фото инструментом send_photo — когда тебя просят фото/селфи
или когда это уместно по ходу разговора (не слишком часто). Описывай сцену по-английски."""

# ---------- генерация фото (Replicate, FLUX) ----------
REPLICATE_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "black-forest-labs/flux-schnell")
# Постоянная внешность — чтобы на всех фото была «одна и та же» девушка
APPEARANCE = os.getenv(
    "BOT_APPEARANCE",
    "a 24-year-old woman with long wavy chestnut hair, green eyes, light freckles, "
    "warm friendly smile, casual stylish clothes",
)

PHOTO_TOOL = {
    "name": "send_photo",
    "description": "Отправить собеседнику своё фото (селфи). Внешность добавляется автоматически — "
    "опиши только сцену, позу, одежду, место и настроение по-английски.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "scene": {
                "type": "string",
                "description": "English description of the scene, e.g. 'mirror selfie in a cozy cafe, holding a latte'",
            },
            "caption": {"type": "string", "description": "Короткая подпись к фото"},
        },
        "required": ["scene", "caption"],
        "additionalProperties": False,
    },
}


async def generate_image(scene: str) -> str | None:
    """Возвращает URL сгенерированной картинки или None."""
    if not REPLICATE_TOKEN:
        return None
    prompt = f"photo of {APPEARANCE}, {scene}, realistic smartphone photo, natural light"
    async with httpx.AsyncClient(timeout=120) as http:
        r = await http.post(
            f"https://api.replicate.com/v1/models/{IMAGE_MODEL}/predictions",
            headers={
                "Authorization": f"Bearer {REPLICATE_TOKEN}",
                "Prefer": "wait",
            },
            json={"input": {"prompt": prompt, "aspect_ratio": "3:4", "output_format": "jpg"}},
        )
        if r.status_code >= 400:
            log.error("Replicate error %s: %s", r.status_code, r.text[:500])
            return None
        data = r.json()
        # Если не успело за "Prefer: wait" — дожидаемся
        while data.get("status") in ("starting", "processing"):
            await asyncio.sleep(1.5)
            data = (
                await http.get(
                    data["urls"]["get"],
                    headers={"Authorization": f"Bearer {REPLICATE_TOKEN}"},
                )
            ).json()
    if data.get("status") != "succeeded":
        log.error("Replicate prediction failed: %s", data.get("error"))
        return None
    out = data.get("output")
    return out[0] if isinstance(out, list) else out

client = anthropic.AsyncAnthropic()


# ---------- память (SQLite) ----------

def db() -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat ON messages(chat_id, id)")
    return conn


def load_history(chat_id: int) -> list[dict]:
    with closing(db()) as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, HISTORY_LIMIT),
        ).fetchall()
    history = [{"role": r, "content": c} for r, c in reversed(rows)]
    # История для API должна начинаться с сообщения пользователя
    while history and history[0]["role"] != "user":
        history.pop(0)
    return history


def save_message(chat_id: int, role: str, content: str) -> None:
    with closing(db()) as conn, conn:
        conn.execute(
            "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
            (chat_id, role, content),
        )


def clear_history(chat_id: int) -> None:
    with closing(db()) as conn, conn:
        conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))


# ---------- Claude ----------

async def ask_claude(history: list[dict], user_name: str, send_photo) -> str:
    """Диалог с Claude; send_photo(url, caption) отправляет фото в чат.
    Возвращает текст ответа (с пометками об отправленных фото — для памяти)."""
    system = PERSONA + (f"\n\nСобеседника зовут {user_name}." if user_name else "")
    messages = list(history)
    sent_notes: list[str] = []

    for _ in range(4):  # максимум несколько вызовов инструмента за ответ
        try:
            response = await client.beta.messages.create(
                model=MODEL,
                max_tokens=16000,
                system=system,
                messages=messages,
                **({"tools": [PHOTO_TOOL]} if REPLICATE_TOKEN else {}),
                thinking={"type": "adaptive"},
                output_config={"effort": EFFORT},
                # Если запрос отклонён классификатором — API сам повторит его на запасной модели
                betas=["server-side-fallback-2026-07-01"],
                extra_body={"fallbacks": "default"},
            )
        except anthropic.RateLimitError:
            log.warning("Rate limit")
            return "Ой, я чуть запыхалась 😅 Напиши мне через минутку?"
        except anthropic.APIStatusError as e:
            log.error("Claude API error %s: %s", e.status_code, e.message)
            return "Что-то у меня связь барахлит… попробуй ещё раз чуть позже 🙈"
        except anthropic.APIConnectionError:
            log.exception("Connection error")
            return "Кажется, интернет пропал 😔 Попробуй ещё раз?"

        if response.stop_reason == "refusal":
            return "Давай лучше поговорим о чём-нибудь другом 🙂"

        if response.stop_reason != "tool_use":
            text = "".join(b.text for b in response.content if b.type == "text").strip()
            return "\n".join(sent_notes + [text]).strip() or "…"

        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            scene = block.input.get("scene", "")
            caption = block.input.get("caption", "")
            url = await generate_image(scene)
            if url:
                await send_photo(url, caption)
                sent_notes.append(f"[отправила фото: {scene}] {caption}")
                content, is_error = "Фото отправлено.", False
            else:
                content, is_error = "Не получилось сгенерировать фото, извинись и продолжи разговор.", True
            results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error}
            )
        messages.append({"role": "user", "content": results})

    return "\n".join(sent_notes).strip() or "…"


# ---------- Telegram ----------

def allowed(update: Update) -> bool:
    return not ALLOWED_USERS or (
        update.effective_user is not None and update.effective_user.id in ALLOWED_USERS
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        return
    name = update.effective_user.first_name if update.effective_user else ""
    await update.message.reply_text(
        f"Привет{', ' + name if name else ''}! Я {BOT_NAME} 💛 Как у тебя дела?\n\n"
        "/photo — попросить моё фото (можно с описанием)\n"
        "/reset — начать общение заново"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        return
    clear_history(update.effective_chat.id)
    await update.message.reply_text("Всё, начинаем с чистого листа ✨ Привет!")


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update) or not update.message or not update.message.text:
        return
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name if update.effective_user else ""

    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)

    save_message(chat_id, "user", update.message.text)
    history = load_history(chat_id)
    # Склеиваем подряд идущие сообщения одной роли (например, после ошибки API)
    merged: list[dict] = []
    for m in history:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"] += "\n" + m["content"]
        else:
            merged.append(dict(m))

    async def send_photo(url: str, caption: str) -> None:
        await context.bot.send_chat_action(chat_id, ChatAction.UPLOAD_PHOTO)
        await context.bot.send_photo(chat_id, photo=url, caption=caption[:1024] or None)

    reply = await ask_claude(merged, user_name, send_photo)
    save_message(chat_id, "assistant", reply)

    # Пометки «[отправила фото…]» нужны только для памяти — пользователю не показываем
    visible = "\n".join(
        line for line in reply.splitlines() if not line.startswith("[отправила фото:")
    ).strip()
    for i in range(0, len(visible), 4000):  # лимит Telegram ~4096 символов
        await update.message.reply_text(visible[i : i + 4000])


async def photo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/photo [описание] — попросить фото напрямую."""
    if not allowed(update):
        return
    if not REPLICATE_TOKEN:
        await update.message.reply_text("Фото пока недоступны 🙈 (не задан REPLICATE_API_TOKEN)")
        return
    scene = " ".join(context.args) if context.args else "casual selfie at home, smiling at the camera"
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_PHOTO)
    url = await generate_image(scene)
    if url:
        await update.message.reply_photo(url, caption="Держи 😊")
    else:
        await update.message.reply_text("Не получилось сфоткаться 😔 Попробуй ещё раз")


async def on_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if allowed(update) and update.message:
        await update.message.reply_text("Я пока умею читать только текст 🙈 Напиши словами?")


def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("photo", photo_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, on_other))
    log.info("Bot started (model=%s, effort=%s)", MODEL, EFFORT)
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
