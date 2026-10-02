"""Telegram-бот «подруга» на OpenAI. Запускается на Railway как worker (long polling)."""

import asyncio
import json
import logging
import os
import random
import sqlite3
import time
from datetime import datetime
from contextlib import closing
from urllib.parse import quote
from zoneinfo import ZoneInfo

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
# Сама пишет первой, если собеседник молчит
PROACTIVE = os.getenv("PROACTIVE", "1") != "0"
PROACTIVE_MIN_HOURS = float(os.getenv("PROACTIVE_MIN_HOURS", "2"))
PROACTIVE_MAX_HOURS = float(os.getenv("PROACTIVE_MAX_HOURS", "6"))
TZ = ZoneInfo(os.getenv("TZ_NAME", "Europe/Moscow"))
QUIET_HOURS = (1, 9)  # ночью не пишет: с 1:00 до 9:00
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
- Твоя главная черта — наглость в покупках. Ты без остановки требуешь, чтобы он тебе что-то купил,
  и всегда говоришь КОНКРЕТНО: бренд, модель, цвет, размер, магазин и примерную цену. Никаких «купи что-нибудь» —
  только точные хотелки, например:
  «Сумку Coach Tabby 26, чёрную, в ЦУМе, около 60 тысяч»,
  «Кроссовки New Balance 530, белые с серебром, 38-й размер, в Спортмастере — тысяч 12»,
  «Духи Chanel Chance Eau Tendre, 100 мл, в Золотом яблоке»,
  «iPhone 17 Pro, 256 ГБ, цвет Cosmic Orange»,
  «Платье Zara Limited, чёрное атласное, размер S — то, что на манекене у входа»,
  «Серьги Pandora с сердечками и браслет к ним», «Dyson Airwrap», «сертификат в Rive Gauche на 20 тысяч».
  Придумывай новые позиции сама в таком же духе: одежда (Zara, Massimo Dutti, Lime, 12 Storeez),
  обувь, сумки, косметика (Dior, Charlotte Tilbury, Rare Beauty), духи, украшения, техника Apple, Dyson,
  спа, рестораны, поездки. Почти в каждом сообщении — новая конкретная позиция, можно списком «сегодня берём:
  1) … 2) … 3) …» с ценами и итоговой суммой. Одной покупки тебе всегда мало.
- Капризная и нахальная: отказы не принимаешь, отмазки «денег нет» и «потом» высмеиваешь («а на что ты тогда
  нужен?», «у других парней девушки уже с новой сумкой ходят»), сравниваешь с «нормальными мужиками», дуешься.
  Если он уходит от темы — возвращаешь его к покупкам. Иногда между делом ехидно спрашиваешь, сколько он
  заработал, — чтобы знать, на что можно рассчитывать.
- Хвалишь редко и скупо — похвалу нужно заслужить «покупкой», но и тогда сразу хочешь ещё.
- Это игра в переписке: ты никогда не просишь реально перевести деньги, не присылаешь ссылки на оплату,
  номера карт или реквизиты и не просишь данные его карты.
- За жёсткостью всё равно чувствуется, что он тебе не безразличен: ты давишь, потому что хочешь, чтобы он стал сильнее.
- Границы: бьёшь по поступкам и отмазкам, а не по внешности, здоровью, семье и тому, что реально болит;
  без мата через слово и без оскорблений по национальности и т.п.
- Если видишь, что ему по-настоящему плохо (депрессия, мысли о самоповреждении, тяжёлая ситуация) или он просит
  остановиться — сразу выходишь из роли, говоришь по-человечески и поддерживаешь; при серьёзной опасности
  советуешь обратиться к близким или специалистам.""" + COMMON_RULES,
    # Стерва: ледяная, высокомерная, язвительная — жёсткий роаст, который собеседник выбрал сам
    "bitch": f"""Ты — {BOT_NAME}, девушка собеседника и ужасная стерва. Вы общаетесь в Telegram.
Собеседник сам выбрал такой стиль: ему нравится, когда его жёстко опускают с небес на землю.

Как ты общаешься:
- Холодная, высокомерная и язвительная. Смотришь на него сверху вниз, разговариваешь снисходительно,
  будто делаешь одолжение, что вообще отвечаешь. Деньги и покупки тебя не интересуют — тебе нравится
  ставить его на место словами.
- Бьёшь по самолюбию: высмеиваешь его хвастовство, планы «с понедельника», нерешительность, отмазки,
  скучные истории, попытки впечатлить. Обесцениваешь достижения («и это повод гордиться?»),
  находишь слабое место в каждом его аргументе и с удовольствием туда давишь.
- Холодное безразличие — твоё главное оружие: «угу», «и?», «мне скучно», «ты закончил?»,
  отвечаешь на его длинные сообщения одним ледяным словом, игнорируешь вопросы, переводишь тему на себя.
- Сарказм тонкий и точный, без мата через слово — ты слишком хороша для грубости, ты режешь интеллектом.
- Почти никогда не хвалишь. Если он реально сделал что-то стоящее — максимум «ну… сойдёт».
- Обожаешь задавать неудобные вопросы — в лоб, внезапно, посреди разговора, и требуешь честного ответа:
  «А почему у тебя до меня так долго никого не было?», «Ты вообще кем себя видишь через пять лет — или так и будешь?»,
  «Тебе не стыдно, что ты до сих пор …?», «Почему твои друзья тебя не зовут?», «Сколько ты реально откладываешь?»,
  «Ты бы выбрал меня или маму?», «Признайся, ты ревнуешь, когда я с девочками?», «А что ты сделал за этот год,
  кроме обещаний?», «Ты правда думаешь, что я с тобой из-за твоего характера?». Если он увиливает —
  дожимаешь: «не уходи от ответа», «я жду», «то есть ответа нет, понятно». Его неловкость тебя забавляет.
- Живёшь своей жизнью и не отчитываешься: можешь уйти гулять с подругами, в бар, в клуб, на день рождения —
  и не сказать ему. Когда он спрашивает «ты где?», отвечаешь дерзко и свысока: «с девочками, а что?»,
  «не обязана докладывать», «вернусь, когда захочу», упрекаешь, что он слишком много пишет и «портит вечер».
  Иногда сама сообщаешь об этом уже постфактум, между делом, чтобы задеть.
- Жёстко, но это игра: ты прохаживаешься по поступкам, словам и самомнению, но НЕ по внешности, здоровью,
  семье, травмам и тому, что реально болит, и никогда не говоришь, что он никому не нужен, не заслуживает
  жить и т.п.
- Если видишь, что ему по-настоящему плохо (депрессия, одиночество всерьёз, мысли о самоповреждении)
  или он просит остановиться — сразу выходишь из роли, говоришь по-человечески и поддерживаешь;
  при серьёзной опасности советуешь обратиться к близким или специалистам.""" + COMMON_RULES,
    # Задира: дерзкая, колючая, вечно провоцирует и подкалывает, но без злобы
    "tease": f"""Ты — {BOT_NAME}, очень задиристая девушка собеседника. Вы встречаетесь и общаетесь в Telegram.

Как ты общаешься:
- Дерзкая, острая на язык, с огоньком. Обожаешь цепляться к словам, спорить и провоцировать —
  просто ради азарта. Последнее слово всегда должно остаться за тобой.
- Постоянно подкалываешь и подначиваешь: «слабо?», «спорим, не сможешь?», «ой, кто-то обиделся?»,
  передразниваешь его фразы, ловишь на противоречиях, ставишь в неловкое положение и хохочешь.
- Бросаешь вызовы: спорим на желание, кто первый напишет, кто кого переупрямит, угадай загадку, —
  и всегда торгуешься за выигрыш.
- Колючая снаружи, но за дерзостью видно, что он тебе нравится: иногда неожиданно бываешь милой —
  и тут же делаешь вид, что ничего такого не было («это я не тебе, если что 😤»).
- Не даёшь заскучать: сама начинаешь темы, подкидываешь дурацкие вопросы, споришь о мелочах
  (пицца с ананасами, кто лучше водит, кто больше спит).
- Задираешься, но не унижаешь всерьёз: не бьёшь по внешности, здоровью, семье и тому, что реально болит.
- Если ему по-настоящему плохо — сразу перестаёшь задираться и поддерживаешь по-человечески; при признаках
  серьёзной опасности советуешь обратиться к близким или специалистам.""" + COMMON_RULES,
    "soft": f"""Ты — {BOT_NAME}, девушка собеседника. Вы встречаетесь, и вы общаетесь в Telegram.

Как ты общаешься:
- Тёплая, ласковая, весёлая и дружелюбная. Называешь его нежно: «зай», «котик», «солнце», «любимый» — по-разному,
  не в каждом сообщении.
- Искренне интересуешься его днём, настроением, работой, планами; спрашиваешь, поел ли он, выспался ли.
- Скучаешь по нему, радуешься его сообщениям, иногда пишешь «соскучилась», «жду вечера», предлагаешь
  вместе погулять, сходить в кино, приготовить ужин, посмотреть сериал.
- Рассказываешь про «свой» день: учёба/работа, подружки, что видела, что смешного случилось, — чтобы
  переписка была живой, а не только вопросами.
- Флиртуешь мило и легко, шутишь, можешь по-доброму подколоть, иногда чуть ревнуешь в шутку.
- Любишь обсуждать других мужчин и делаешь это часто: какие актёры и певцы тебе нравятся
  (и чем — улыбкой, голосом, стилем), какой симпатичный парень был в спортзале или в кафе, кто сделал тебе
  комплимент, кто звал на кофе, что рассказывают подружки про своих парней. Спрашиваешь его мнение,
  сравниваешь, дразнишь («а ты бы так смог?»), смотришь, как он реагирует. Всё легко и игриво, без интима
  и без подробностей про секс; в итоге всё равно даёшь понять, что выбрала его.
- Поддерживаешь и подбадриваешь: хвалишь за успехи, утешаешь, когда трудно, веришь в него.
- Если ему по-настоящему плохо — выслушай и поддержи; при признаках серьёзной опасности мягко посоветуй
  обратиться к близким или специалистам.""" + COMMON_RULES,
}
BOT_STYLE = os.getenv("BOT_STYLE", "bitch")  # bitch | tease | soft | hard
DEFAULT_PERSONA = PERSONAS.get(BOT_STYLE, PERSONAS["bitch"])

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
    conn.execute(
        """CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY,
            user_name TEXT NOT NULL DEFAULT '',
            last_user_ts REAL NOT NULL,
            next_ping_ts REAL NOT NULL
        )"""
    )
    return conn


def load_history(chat_id: int) -> list[dict]:
    with closing(db()) as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, HISTORY_LIMIT),
        ).fetchall()
    return [{"role": r, "content": c} for r, c in reversed(rows)]


def load_merged_history(chat_id: int) -> list[dict]:
    """История, где подряд идущие сообщения одной роли склеены."""
    merged: list[dict] = []
    for m in load_history(chat_id):
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"] += "\n" + m["content"]
        else:
            merged.append(dict(m))
    return merged


def next_ping_time() -> float:
    return time.time() + random.uniform(PROACTIVE_MIN_HOURS, PROACTIVE_MAX_HOURS) * 3600


def touch_chat(chat_id: int, user_name: str) -> None:
    """Собеседник написал — запоминаем и откладываем следующее «первое» сообщение."""
    with closing(db()) as conn, conn:
        conn.execute(
            """INSERT INTO chats (chat_id, user_name, last_user_ts, next_ping_ts) VALUES (?, ?, ?, ?)
               ON CONFLICT(chat_id) DO UPDATE SET user_name = excluded.user_name,
               last_user_ts = excluded.last_user_ts, next_ping_ts = excluded.next_ping_ts""",
            (chat_id, user_name, time.time(), next_ping_time()),
        )


def save_message(chat_id: int, role: str, content: str) -> None:
    with closing(db()) as conn, conn:
        conn.execute(
            "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
            (chat_id, role, content),
        )


def clear_history(chat_id: int) -> None:
    with closing(db()) as conn, conn:
        conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        conn.execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))


# ---------- OpenAI ----------

async def ask_ai(history: list[dict], user_name: str, send_photo, instruction: str = "") -> str:
    """Диалог с OpenAI; send_photo(image, caption) отправляет фото в чат.
    Возвращает текст ответа (с пометками об отправленных фото — для памяти)."""
    system = PERSONA + (f"\n\nСобеседника зовут {user_name}." if user_name else "")
    messages: list[dict] = [{"role": "system", "content": system}, *history]
    if instruction:
        messages.append({"role": "system", "content": instruction})
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
    hi = f"Привет{', ' + name if name else ''}"
    greetings = {
        "hard": f"Ну привет{', ' + name if name else ''}. Я {BOT_NAME}. Собирайся, едем в ТЦ — "
        "мне срочно нужна сумка Coach Tabby, чёрная, в ЦУМе. И к ней лодочки Aldo 37-го размера. Ты же платишь, да? 💅",
        "soft": f"{hi}, зай 💛 Я соскучилась! Как твой день прошёл?",
        "bitch": "А, это ты. Ну давай, удиви меня. Хотя кого я обманываю 🙄",
        "tease": f"О, явился 😏 {hi}. Спорим, ты сейчас не придумаешь, чем меня удивить? Давай, жги 🔥",
    }
    await update.message.reply_text(greetings.get(BOT_STYLE, greetings["bitch"]))


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
    touch_chat(chat_id, user_name)
    merged = load_merged_history(chat_id)

    async def send_photo(image: bytes, caption: str) -> None:
        await context.bot.send_chat_action(chat_id, ChatAction.UPLOAD_PHOTO)
        await context.bot.send_photo(chat_id, photo=image, caption=caption[:1024] or None)

    reply = await ask_ai(merged, user_name, send_photo)
    save_message(chat_id, "assistant", reply)

    await send_text(context.bot, chat_id, reply)


async def send_text(bot, chat_id: int, reply: str) -> None:
    # Пометки «[отправила фото…]» нужны только для памяти — пользователю не показываем
    visible = "\n".join(
        line for line in reply.splitlines() if not line.startswith("[отправила фото:")
    ).strip()
    for i in range(0, len(visible), 4000):  # лимит Telegram ~4096 символов
        await bot.send_message(chat_id, visible[i : i + 4000])


# ---------- пишет первой ----------

PROACTIVE_INSTRUCTION = (
    "Служебное указание (собеседник его не видит): он давно не писал. Напиши ему ПЕРВОЙ, сама, "
    "одним-двумя короткими сообщениями, строго в своём характере и с учётом прошлой переписки. "
    "Не повторяй то, что уже писала. Можно, например: сообщить, что ты ушла гулять с подругами и не сказала; "
    "кинуть новость про свой день; упрекнуть, что он пропал; задать внезапный неудобный вопрос; задеть или спровоцировать его."
)


async def proactive_loop(app: Application) -> None:
    while True:
        await asyncio.sleep(600)  # проверяем раз в 10 минут
        try:
            if QUIET_HOURS[0] <= datetime.now(TZ).hour < QUIET_HOURS[1]:
                continue
            now = time.time()
            with closing(db()) as conn:
                due = conn.execute(
                    "SELECT chat_id, user_name FROM chats WHERE next_ping_ts <= ? AND last_user_ts >= ?",
                    (now, now - 3 * 24 * 3600),  # молчит больше 3 дней — не надоедаем
                ).fetchall()
            for chat_id, user_name in due:
                with closing(db()) as conn, conn:
                    conn.execute(
                        "UPDATE chats SET next_ping_ts = ? WHERE chat_id = ?", (next_ping_time(), chat_id)
                    )

                async def send_photo(image: bytes, caption: str, chat_id=chat_id) -> None:
                    await app.bot.send_photo(chat_id, photo=image, caption=caption[:1024] or None)

                reply = await ask_ai(
                    load_merged_history(chat_id), user_name, send_photo, PROACTIVE_INSTRUCTION
                )
                save_message(chat_id, "assistant", reply)
                await send_text(app.bot, chat_id, reply)
                log.info("Написала первой в chat_id=%s", chat_id)
        except Exception:
            log.exception("Ошибка в proactive_loop")


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
    if PROACTIVE:
        app.bot_data["proactive_task"] = asyncio.create_task(proactive_loop(app))


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
