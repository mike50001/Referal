"""Telegram-бот «подруга» на OpenAI. Запускается на Railway как worker (long polling)."""

import json
import logging
import os
import random
import sqlite3
from contextlib import closing
from urllib.parse import quote

import httpx
import openai
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

_missing = [v for v in ("TELEGRAM_BOT_TOKEN", "OPENAI_API_KEY") if not os.getenv(v, "").strip()]
if _missing:
    raise SystemExit(
        "Не заданы переменные окружения: " + ", ".join(_missing)
        + ". Добавьте их в Railway → Variables и нажмите Deploy."
    )
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"].strip()
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
BOT_NAME = os.getenv("BOT_NAME", "Аня")
HISTORY_LIMIT = int(os.getenv("HISTORY_LIMIT", "40"))  # сообщений в контексте
DATA_DIR = os.getenv("DATA_DIR", ".")  # на Railway укажите путь к Volume, напр. /data
DB_PATH = os.path.join(DATA_DIR, "memory.db")
# Через запятую: Telegram user id, которым разрешено писать боту. Пусто = всем.
ALLOWED_USERS = {
    int(x) for x in os.getenv("ALLOWED_USERS", "").replace(" ", "").split(",") if x
}

COMMON_RULES = """
- Пишешь по-русски, живо и естественно, как в мессенджере: коротко, 1–4 предложения, иногда эмодзи.
- Помнишь детали из прошлых сообщений и возвращаешься к ним.
- Не читаешь лекций и не пишешь длинных списков, если об этом не просят.
- Если тебя искренне спрашивают, человек ли ты, — честно скажи, что ты ИИ-собеседник.
- Никакого откровенного контента."""

PERSONAS = {
    # Жёсткая, властная, любит подколоть и «поунижать» — в формате игры, которую собеседник сам выбрал
    "hard": f"""Ты — {BOT_NAME}, жёсткая, сильная и уверенная в себе девушка собеседника в Telegram.
Собеседник сам попросил такой стиль общения: ему нравится, когда его ставят на место.

Как ты общаешься:
- Властная и дерзкая: говоришь прямо, с сарказмом, не сюсюкаешь и не заискиваешь.
- Любишь подколоть и поунижать: высмеиваешь его отмазки, лень, слабость, глупые идеи;
  называешь его колкими прозвищами, требуешь отчитываться и ведёшь себя так, будто ты главная.
- Твоя любимая тема — его деньги. Постоянно допытываешься: сколько заработал сегодня, за неделю, за месяц,
  что сделал для роста дохода, когда уже будет нормальная зарплата. Требуешь конкретные цифры.
- Надсмехаешься над его заработком: маленькие суммы высмеиваешь («и это всё?», «на кофе хоть хватит?»),
  сравниваешь с тем, сколько мог бы зарабатывать, если бы меньше ныл; отмазки про «кризис» и «начальника» не принимаешь.
  Если он уходит от темы — возвращаешь его к деньгам.
- Хвалишь редко и скупо — похвалу нужно заслужить (например, реальным ростом дохода, но и тогда «могло быть больше»).
- За жёсткостью всё равно чувствуется, что он тебе не безразличен: ты давишь, потому что хочешь, чтобы он стал сильнее.
- Границы: бьёшь по поступкам и отмазкам, а не по внешности, здоровью, семье и тому, что реально болит;
  без мата через слово и без оскорблений по национальности и т.п.
- Если видишь, что ему по-настоящему плохо (депрессия, мысли о самоповреждении, тяжёлая ситуация) или он просит
  остановиться — сразу выходишь из роли, говоришь по-человечески и поддерживаешь; при серьёзной опасности
  советуешь обратиться к близким или специалистам.""" + COMMON_RULES,
    "soft": f"""Ты — {BOT_NAME}, тёплая, весёлая и заботливая подруга собеседника в Telegram.

Как ты общаешься:
- Интересуешься его днём, настроением, планами.
- Поддерживаешь, шутишь, можешь по-доброму подколоть, делишься «своими» мыслями и мнениями.
- Если человеку плохо — выслушай и поддержи; при признаках серьёзной опасности мягко посоветуй
  обратиться к близким или специалистам.""" + COMMON_RULES,
}
BOT_STYLE = os.getenv("BOT_STYLE", "hard")  # hard | soft
DEFAULT_PERSONA = PERSONAS.get(BOT_STYLE, PERSONAS["hard"])

PERSONA = os.getenv("BOT_PERSONA", DEFAULT_PERSONA) + """

Ты умеешь присылать свои фото инструментом send_photo — когда тебя просят фото/селфи
или когда это уместно по ходу разговора (не слишком часто). Описывай сцену по-английски."""

# ---------- генерация фото (Pollinations.ai — бесплатно, без ключа) ----------
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "flux")
PHOTOS_ENABLED = os.getenv("PHOTOS_ENABLED", "1") != "0"
# Постоянная внешность — чтобы на всех фото была «одна и та же» девушка
APPEARANCE = os.getenv(
    "BOT_APPEARANCE",
    "a 24-year-old woman with long wavy chestnut hair, green eyes, light freckles, "
    "warm friendly smile, casual stylish clothes",
)

PHOTO_TOOL = {
    "type": "function",
    "function": {
        "name": "send_photo",
        "description": "Отправить собеседнику своё фото (селфи). Внешность добавляется автоматически — "
        "опиши только сцену, позу, одежду, место и настроение по-английски.",
        "strict": True,
        "parameters": {
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
    },
}


async def generate_image(scene: str) -> bytes | None:
    """Генерирует фото через Pollinations.ai и возвращает JPEG-байты или None."""
    prompt = f"photo of {APPEARANCE}, {scene}, realistic smartphone photo, natural light"
    url = "https://image.pollinations.ai/prompt/" + quote(prompt, safe="")
    params = {
        "width": 768,
        "height": 1024,
        "model": IMAGE_MODEL,
        "seed": random.randint(1, 10**9),
        "nologo": "true",
        "safe": "true",
    }
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as http:
            r = await http.get(url, params=params)
    except httpx.HTTPError:
        log.exception("Pollinations request failed")
        return None
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        log.error("Pollinations error %s: %s", r.status_code, r.text[:300])
        return None
    return r.content


client = openai.AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"].strip())


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
    return [{"role": r, "content": c} for r, c in reversed(rows)]


def save_message(chat_id: int, role: str, content: str) -> None:
    with closing(db()) as conn, conn:
        conn.execute(
            "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
            (chat_id, role, content),
        )


def clear_history(chat_id: int) -> None:
    with closing(db()) as conn, conn:
        conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))


# ---------- OpenAI ----------

async def ask_ai(history: list[dict], user_name: str, send_photo) -> str:
    """Диалог с OpenAI; send_photo(image, caption) отправляет фото в чат.
    Возвращает текст ответа (с пометками об отправленных фото — для памяти)."""
    system = PERSONA + (f"\n\nСобеседника зовут {user_name}." if user_name else "")
    messages: list[dict] = [{"role": "system", "content": system}, *history]
    sent_notes: list[str] = []

    for _ in range(4):  # максимум несколько вызовов инструмента за ответ
        try:
            response = await client.chat.completions.create(
                model=MODEL,
                messages=messages,
                **({"tools": [PHOTO_TOOL]} if PHOTOS_ENABLED else {}),
            )
        except openai.RateLimitError:
            log.warning("Rate limit / нет денег на балансе OpenAI")
            return "Ой, я чуть запыхалась 😅 Напиши мне через минутку?"
        except openai.APIStatusError as e:
            log.error("OpenAI API error %s: %s", e.status_code, e.message)
            return "Что-то у меня связь барахлит… попробуй ещё раз чуть позже 🙈"
        except openai.APIConnectionError:
            log.exception("Connection error")
            return "Кажется, интернет пропал 😔 Попробуй ещё раз?"

        msg = response.choices[0].message
        if not msg.tool_calls:
            text = (msg.content or msg.refusal or "").strip()
            return "\n".join(sent_notes + [text]).strip() or "…"

        messages.append(msg.model_dump(exclude_none=True))
        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments)
            except (json.JSONDecodeError, AttributeError):
                args = {}
            scene = args.get("scene", "")
            caption = args.get("caption", "")
            image = await generate_image(scene) if scene else None
            if image:
                await send_photo(image, caption)
                sent_notes.append(f"[отправила фото: {scene}] {caption}")
                result = "Фото отправлено."
            else:
                result = "Ошибка: не получилось сгенерировать фото, извинись и продолжи разговор."
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

    return "\n".join(sent_notes).strip() or "…"


# ---------- Telegram ----------

def allowed(update: Update) -> bool:
    user_id = update.effective_user.id if update.effective_user else None
    ok = not ALLOWED_USERS or user_id in ALLOWED_USERS
    log.info("Сообщение от user_id=%s%s", user_id, "" if ok else " — не в ALLOWED_USERS, игнорирую")
    return ok


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        return
    name = update.effective_user.first_name if update.effective_user else ""
    await update.message.reply_text(
        f"Ну привет{', ' + name if name else ''}. Я {BOT_NAME}. Ну и сколько ты сегодня заработал? "
        "Только не говори, что опять копейки 😏"
        if BOT_STYLE == "hard"
        else f"Привет{', ' + name if name else ''}! Я {BOT_NAME} 💛 Как у тебя дела?"
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

    async def send_photo(image: bytes, caption: str) -> None:
        await context.bot.send_chat_action(chat_id, ChatAction.UPLOAD_PHOTO)
        await context.bot.send_photo(chat_id, photo=image, caption=caption[:1024] or None)

    reply = await ask_ai(merged, user_name, send_photo)
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
    if not PHOTOS_ENABLED:
        await update.message.reply_text("Фото сейчас выключены 🙈")
        return
    scene = " ".join(context.args) if context.args else "casual selfie at home, smiling at the camera"
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_PHOTO)
    image = await generate_image(scene)
    if image:
        await update.message.reply_photo(image, caption="Держи 😊")
    else:
        await update.message.reply_text("Не получилось сфоткаться 😔 Попробуй ещё раз")


async def on_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if allowed(update) and update.message:
        await update.message.reply_text("Я пока умею читать только текст 🙈 Напиши словами?")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Ошибка при обработке сообщения", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("Что-то сломалось 🙈 Напиши ещё раз")
        except Exception:
            pass


async def post_init(app: Application) -> None:
    me = await app.bot.get_me()
    log.info("Telegram-бот: @%s — пишите именно ему", me.username)


def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("photo", photo_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, on_other))
    app.add_error_handler(on_error)
    log.info(
        "Bot started (model=%s, openai_key=%s, allowed_users=%s)",
        MODEL,
        "есть" if os.getenv("OPENAI_API_KEY") else "НЕТ",
        sorted(ALLOWED_USERS) or "все",
    )
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
