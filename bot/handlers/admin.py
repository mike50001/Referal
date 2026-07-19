"""Хендлеры админ-части: ответ клиенту reply-сообщением на заявку.

Роутинг ответа полностью бесстостоянийный: ID клиента зашит в текст
заявки (маркер CLIENT_ID_MARKER), поэтому ответы работают даже после
перезапуска бота — без базы данных.
"""
from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot import rates
from bot.config import Config
from bot.states import SetRates

router = Router(name="admin")

# Импортируем внутри модуля клиента, чтобы избежать цикла импорта на уровне модуля.
from bot.handlers.client import CLIENT_ID_MARKER  # noqa: E402

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

_SETRATE_STEPS = [
    (SetRates.kzt_give_kzt, "kzt_give_kzt",
     "1️⃣ Тенге → Рубль: сколько <b>тенге за 1 рубль</b>, когда клиент отдаёт ТЕНГЕ?"),
    (SetRates.kzt_give_rub, "kzt_give_rub",
     "2️⃣ Рубль → Тенге: сколько <b>тенге за 1 рубль</b>, когда клиент отдаёт РУБЛИ?"),
    (SetRates.thb_give_thb, "thb_give_thb",
     "3️⃣ Бат → Рубль: сколько <b>рублей за 1 бат</b>, когда клиент отдаёт БАТЫ?"),
    (SetRates.thb_give_rub, "thb_give_rub",
     "4️⃣ Рубль → Бат: сколько <b>рублей за 1 бат</b>, когда клиент отдаёт РУБЛИ?"),
]


@router.message(Command("setrate"))
async def setrate_start(
    message: Message, command: CommandObject, state: FSMContext, config: Config
) -> None:
    if not _is_admin_chat(message, config):
        return

    # Быстрый путь: /setrate 6.2 5.6 2.3 2.55 (тенге→руб, руб→тенге, бат→руб, руб→бат)
    if command.args:
        parts = command.args.split()
        if len(parts) == 4:
            values = [_parse_rate(p) for p in parts]
            if all(v is not None for v in values):
                rates.set_quotes(*values)  # type: ignore[arg-type]
                await state.clear()
                await message.answer(
                    "✅ Курсы обновлены!\n\n" + await rates.snapshot_text()
                )
                return
        await message.answer(
            "Формат: <code>/setrate 6.2 5.6 2.3 2.55</code>\n"
            "(тенге→руб, руб→тенге, бат→руб, руб→бат)\n\n"
            "Или отправьте просто /setrate — задам по шагам."
        )
        return

    # Пошаговый путь.
    quotes = rates.get_quotes()
    await state.set_state(SetRates.kzt_give_kzt)
    await message.answer(
        "Обновление курсов. Отправьте /cancel для отмены.\n\n"
        f"Сейчас: {quotes['kzt_give_kzt']:g} / {quotes['kzt_give_rub']:g} / "
        f"{quotes['thb_give_thb']:g} / {quotes['thb_give_rub']:g}\n\n"
        + _SETRATE_STEPS[0][2]
    )


async def _setrate_step(message: Message, state: FSMContext, index: int) -> None:
    value = _parse_rate(message.text or "")
    if value is None:
        await message.answer("Введите число больше нуля. Например: 6.2")
        return
    _, key, _ = _SETRATE_STEPS[index]
    await state.update_data(**{key: value})

    if index + 1 < len(_SETRATE_STEPS):
        next_state, _, prompt = _SETRATE_STEPS[index + 1]
        await state.set_state(next_state)
        await message.answer(prompt)
    else:
        data = await state.get_data()
        rates.set_quotes(
            data["kzt_give_kzt"], data["kzt_give_rub"],
            data["thb_give_thb"], data["thb_give_rub"],
        )
        await state.clear()
        await message.answer("✅ Курсы обновлены!\n\n" + await rates.snapshot_text())


@router.message(SetRates.kzt_give_kzt)
async def setrate_1(message: Message, state: FSMContext) -> None:
    await _setrate_step(message, state, 0)


@router.message(SetRates.kzt_give_rub)
async def setrate_2(message: Message, state: FSMContext) -> None:
    await _setrate_step(message, state, 1)


@router.message(SetRates.thb_give_thb)
async def setrate_3(message: Message, state: FSMContext) -> None:
    await _setrate_step(message, state, 2)


@router.message(SetRates.thb_give_rub)
async def setrate_4(message: Message, state: FSMContext) -> None:
    await _setrate_step(message, state, 3)


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
