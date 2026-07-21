"""Хендлеры админ-части: ответ клиенту reply-сообщением на заявку.

Роутинг ответа полностью бесстостоянийный: ID клиента зашит в текст
заявки (маркер CLIENT_ID_MARKER), поэтому ответы работают даже после
перезапуска бота — без базы данных.
"""
from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot import rates
from bot.config import Config
from bot.states import SetRates

router = Router(name="admin")

# Импортируем внутри модуля клиента, чтобы избежать цикла импорта на уровне модуля.
from bot.handlers.client import CLIENT_ID_MARKER, WELCOME  # noqa: E402
from bot.keyboards import start_keyboard  # noqa: E402

_CLIENT_ID_RE = re.compile(re.escape(CLIENT_ID_MARKER) + r"\s*(\d+)")


def _extract_client_id(text: str | None) -> int | None:
    if not text:
        return None
    match = _CLIENT_ID_RE.search(text)
    return int(match.group(1)) if match else None


def _is_admin_chat(message: Message, config: Config) -> bool:
    return message.chat.id == config.admin_chat_id


def _parse_rate(text: str) -> float | None:
    """Парсит положительное число (с запятой или точкой)."""
    try:
        value = float(text.strip().replace(" ", "").replace(",", "."))
    except (ValueError, AttributeError):
        return None
    return value if value > 0 else None


@router.message(Command("rates"))
async def show_rates(message: Message, config: Config) -> None:
    """Показать текущие курсы. Только в чате заявок."""
    if not _is_admin_chat(message, config):
        return
    await message.answer(await rates.snapshot_text())


# --- Изменение курсов: /setrate -------------------------------------------

# Порядок ввода/показа: тенге→руб, руб→тенге, руб→бат, бат→руб.
_SETRATE_STEPS = [
    (SetRates.kzt_give_kzt, "kzt_give_kzt",
     "1️⃣ Тенге → Рубль: сколько <b>тенге за 1 рубль</b>, когда клиент отдаёт ТЕНГЕ?"),
    (SetRates.kzt_give_rub, "kzt_give_rub",
     "2️⃣ Рубль → Тенге: сколько <b>тенге за 1 рубль</b>, когда клиент отдаёт РУБЛИ?"),
    (SetRates.thb_give_rub, "thb_give_rub",
     "3️⃣ Рубль → Бат: сколько <b>рублей за 1 бат</b>, когда клиент отдаёт РУБЛИ?"),
    (SetRates.thb_give_thb, "thb_give_thb",
     "4️⃣ Бат → Рубль: сколько <b>рублей за 1 бат</b>, когда клиент отдаёт БАТЫ?"),
]
# Индекс шага по имени состояния — чтобы порядок задавался только списком выше.
_STEP_INDEX = {st.state: i for i, (st, _, _) in enumerate(_SETRATE_STEPS)}
_SETRATE_STATES = [st for st, _, _ in _SETRATE_STEPS]


@router.message(Command("setrate"))
async def setrate_start(
    message: Message, command: CommandObject, state: FSMContext, config: Config
) -> None:
    if not _is_admin_chat(message, config):
        return

    # Быстрый путь: /setrate 6.0 5.6 2.55 2.33 (тенге→руб, руб→тенге, руб→бат, бат→руб)
    if command.args:
        parts = command.args.split()
        values = [_parse_rate(p) for p in parts] if len(parts) == 4 else []
        if values and all(v is not None for v in values):
            # values идут в порядке _SETRATE_STEPS; раскладываем по ключам.
            by_key = {key: values[i] for i, (_, key, _) in enumerate(_SETRATE_STEPS)}
            rates.set_quotes(
                kzt_give_kzt=by_key["kzt_give_kzt"],
                kzt_give_rub=by_key["kzt_give_rub"],
                thb_give_thb=by_key["thb_give_thb"],
                thb_give_rub=by_key["thb_give_rub"],
            )
            await state.clear()
            await message.answer("✅ Курсы обновлены!\n\n" + await rates.snapshot_text())
            return
        await message.answer(
            "Формат: <code>/setrate 6.0 5.6 2.55 2.33</code>\n"
            "(тенге→руб, руб→тенге, руб→бат, бат→руб)\n\n"
            "Или отправьте просто /setrate — задам по шагам."
        )
        return

    # Пошаговый путь.
    quotes = rates.get_quotes()
    current = " / ".join(f"{quotes[key]:g}" for _, key, _ in _SETRATE_STEPS)
    await state.set_state(_SETRATE_STATES[0])
    await message.answer(
        "Обновление курсов. Отправьте /cancel для отмены.\n\n"
        f"Сейчас: {current}\n\n" + _SETRATE_STEPS[0][2]
    )


@router.message(StateFilter(*_SETRATE_STATES))
async def setrate_step(message: Message, state: FSMContext) -> None:
    index = _STEP_INDEX[await state.get_state()]
    value = _parse_rate(message.text or "")
    if value is None:
        await message.answer("Введите число больше нуля. Например: 6.0")
        return

    _, key, _ = _SETRATE_STEPS[index]
    await state.update_data(**{key: value})

    if index + 1 < len(_SETRATE_STEPS):
        next_state, _, prompt = _SETRATE_STEPS[index + 1]
        await state.set_state(next_state)
        await message.answer(prompt)
        return

    data = await state.get_data()
    rates.set_quotes(
        kzt_give_kzt=data["kzt_give_kzt"], kzt_give_rub=data["kzt_give_rub"],
        thb_give_thb=data["thb_give_thb"], thb_give_rub=data["thb_give_rub"],
    )
    await state.clear()
    await message.answer("✅ Курсы обновлены!\n\n" + await rates.snapshot_text())


@router.message(F.reply_to_message)
async def reply_to_client(message: Message, config: Config) -> None:
    # Реагируем только на ответы, отправленные в чат заявок.
    if message.chat.id != config.admin_chat_id:
        return

    client_id = _extract_client_id(message.reply_to_message.text)
    if client_id is None:
        # Реплай не на сообщение-заявку — игнорируем.
        return

    if not config.is_admin(message.from_user.id):
        await message.reply("У вас нет прав отвечать клиентам.")
        return

    answer = message.text or message.caption
    if not answer:
        await message.reply("Ответ клиенту можно отправить только текстом.")
        return

    try:
        await message.bot.send_message(
            client_id,
            f"💬 <b>Ответ менеджера:</b>\n\n{answer}",
        )
    except Exception:
        await message.reply(
            "⚠️ Не удалось доставить ответ клиенту "
            "(возможно, он остановил бота)."
        )
        return

    await message.reply("✅ Ответ отправлен клиенту.")


# Заглушка последним: любое необработанное сообщение клиента в личке
# возвращает приветствие и меню. Это спасает, когда клиент удалил чат и
# не видит кнопку «Запустить» — достаточно написать боту что угодно.
@router.message(StateFilter(None), F.chat.type == "private")
async def fallback_greeting(message: Message, config: Config) -> None:
    if message.chat.id == config.admin_chat_id:
        return  # чат заявок не трогаем
    await message.answer(WELCOME, reply_markup=start_keyboard())
