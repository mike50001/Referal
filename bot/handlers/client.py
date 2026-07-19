"""Хендлеры клиентской части: приветствие и сбор заявки на обмен."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.keyboards import (
    amount_side_keyboard,
    confirm_keyboard,
    contact_keyboard,
    currency_keyboard,
    start_keyboard,
)
from bot.states import ExchangeForm

router = Router(name="client")

# --- Тексты ---------------------------------------------------------------

WELCOME = (
    "👋 Доброго времени суток!\n\n"
    "Вас приветствует <b>обменник Михаила</b>.\n"
    "⚠️ Остерегайтесь подделок!\n\n"
    "Оставьте заявку — менеджер свяжется с вами и назовёт актуальный курс.\n\n"
    "Нажмите кнопку ниже, чтобы начать."
)

# Маркер, по которому админ-хендлер вычисляет ID клиента при ответе реплаем.
CLIENT_ID_MARKER = "ID клиента:"


# --- Старт и запуск заявки ------------------------------------------------


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(WELCOME, reply_markup=start_keyboard())


@router.message(Command("cancel"))
@router.message(F.text.casefold() == "отмена")
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer("Сейчас нет активной заявки.", reply_markup=start_keyboard())
        return
    await state.clear()
    await message.answer("❌ Заявка отменена.", reply_markup=start_keyboard())


@router.message(F.text == "💱 Оставить заявку на обмен")
@router.message(Command("exchange"))
async def start_form(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(ExchangeForm.give_currency)
    await message.answer(
        "Шаг 1/5. Какую валюту вы <b>отдаёте</b>?",
        reply_markup=currency_keyboard("give"),
    )


# --- Шаг 1: валюта, которую отдают ----------------------------------------


@router.callback_query(ExchangeForm.give_currency, F.data.startswith("give:"))
async def pick_give(call: CallbackQuery, state: FSMContext) -> None:
    _, value = call.data.split(":", 1)
    if value == "custom":
        await call.message.answer("Введите валюту, которую вы отдаёте (например, GBP):")
        await call.answer()
        return
    await state.update_data(give=value)
    await _ask_get_currency(call.message, state)
    await call.answer()


@router.message(ExchangeForm.give_currency, F.text)
async def type_give(message: Message, state: FSMContext) -> None:
    await state.update_data(give=message.text.strip().upper())
    await _ask_get_currency(message, state)


async def _ask_get_currency(message: Message, state: FSMContext) -> None:
    await state.set_state(ExchangeForm.get_currency)
    await message.answer(
        "Шаг 2/5. Какую валюту вы хотите <b>получить</b>?",
        reply_markup=currency_keyboard("get"),
    )


# --- Шаг 2: валюта, которую хотят получить --------------------------------


@router.callback_query(ExchangeForm.get_currency, F.data.startswith("get:"))
async def pick_get(call: CallbackQuery, state: FSMContext) -> None:
    _, value = call.data.split(":", 1)
    if value == "custom":
        await call.message.answer("Введите валюту, которую хотите получить:")
        await call.answer()
        return
    await state.update_data(get=value)
    await _ask_amount_side(call.message, state)
    await call.answer()


@router.message(ExchangeForm.get_currency, F.text)
async def type_get(message: Message, state: FSMContext) -> None:
    await state.update_data(get=message.text.strip().upper())
    await _ask_amount_side(message, state)


async def _ask_amount_side(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(ExchangeForm.amount_side)
    await message.answer(
        "Шаг 3/5. Как удобнее указать сумму?\n\n"
        f"💸 <b>Отдаю</b> — вы называете, сколько отдаёте в {data.get('give')}.\n"
        f"🎯 <b>Хочу получить</b> — вы называете, сколько хотите получить "
        f"в {data.get('get')} (сколько заплатить — рассчитает менеджер).",
        reply_markup=amount_side_keyboard(),
    )


# --- Шаг 3: способ указания суммы -----------------------------------------


@router.callback_query(ExchangeForm.amount_side, F.data.startswith("side:"))
async def pick_amount_side(call: CallbackQuery, state: FSMContext) -> None:
    _, side = call.data.split(":", 1)
    await state.update_data(side=side)
    await _ask_amount(call.message, state)
    await call.answer()


async def _ask_amount(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(ExchangeForm.amount)
    if data.get("side") == "get":
        prompt = (
            f"Шаг 4/5. Сколько вы хотите <b>получить</b>?\n"
            f"Укажите сумму в <b>{data.get('get')}</b> (например, 1000):"
        )
    else:
        prompt = (
            f"Шаг 4/5. Сколько вы хотите <b>отдать</b>?\n"
            f"Укажите сумму в <b>{data.get('give')}</b> (например, 1000):"
        )
    await message.answer(prompt)


# --- Шаг 4: сумма ---------------------------------------------------------


@router.message(ExchangeForm.amount, F.text)
async def type_amount(message: Message, state: FSMContext) -> None:
    raw = message.text.strip().replace(" ", "").replace(",", ".")
    try:
        value = float(raw)
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите сумму числом больше нуля. Например: 1000")
        return

    # Сохраняем как введено (без принудительного форматирования дробей).
    await state.update_data(amount=message.text.strip())
    await state.set_state(ExchangeForm.contact)
    await message.answer(
        "Шаг 5/5. Как с вами связаться?\n"
        "Отправьте номер телефона кнопкой ниже или напишите контакт "
        "(телефон / @username) вручную.",
        reply_markup=contact_keyboard(),
    )


# --- Шаг 4: контакт -------------------------------------------------------


@router.message(ExchangeForm.contact, F.contact)
async def contact_shared(message: Message, state: FSMContext) -> None:
    await state.update_data(contact=message.contact.phone_number)
    await _show_summary(message, state)


@router.message(ExchangeForm.contact, F.text)
async def contact_typed(message: Message, state: FSMContext) -> None:
    await state.update_data(contact=message.text.strip())
    await _show_summary(message, state)


def _amount_lines(data: dict) -> str:
    """Строки о сумме с учётом выбранного способа (отдаю / хочу получить)."""
    give, get, amount = data.get("give"), data.get("get"), data.get("amount")
    if data.get("side") == "get":
        return (
            f"💸 Отдаёте: <b>{give}</b> <i>(сумму рассчитает менеджер)</i>\n"
            f"🎯 Хотите получить: <b>{amount} {get}</b>"
        )
    return (
        f"💸 Отдаёте: <b>{amount} {give}</b>\n"
        f"💰 Получаете: <b>{get}</b> <i>(сумму рассчитает менеджер)</i>"
    )


async def _show_summary(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = (
        "Проверьте заявку:\n\n"
        f"{_amount_lines(data)}\n"
        f"📞 Контакт: <b>{data.get('contact')}</b>\n\n"
        "Всё верно?"
    )
    await state.set_state(ExchangeForm.confirm)
    await message.answer(text, reply_markup=confirm_keyboard())


# --- Подтверждение и отправка админу --------------------------------------


@router.callback_query(ExchangeForm.confirm, F.data == "confirm:no")
async def confirm_no(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer("❌ Заявка отменена.", reply_markup=start_keyboard())
    await call.answer()


@router.callback_query(ExchangeForm.confirm, F.data == "confirm:yes")
async def confirm_yes(call: CallbackQuery, state: FSMContext, config: Config) -> None:
    data = await state.get_data()
    user = call.from_user

    username_part = f" (@{user.username})" if user.username else ""
    admin_text = (
        "🆕 <b>Новая заявка на обмен</b>\n\n"
        f"👤 Клиент: <a href=\"tg://user?id={user.id}\">{user.full_name}</a>"
        f"{username_part}\n"
        f"{_amount_lines(data)}\n"
        f"📞 Контакт: <b>{data.get('contact')}</b>\n\n"
        f"{CLIENT_ID_MARKER} {user.id}\n"
        "↩️ Чтобы ответить клиенту — ответьте (reply) на это сообщение."
    )

    try:
        await call.bot.send_message(config.admin_chat_id, admin_text)
    except Exception:
        await call.answer()
        await call.message.answer(
            "⚠️ Не удалось отправить заявку менеджеру. Попробуйте позже "
            "или напишите нам напрямую."
        )
        return

    await state.clear()
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(
        "✅ Спасибо! Ваша заявка принята.\n"
        "Менеджер скоро свяжется с вами и назовёт актуальный курс.",
        reply_markup=start_keyboard(),
    )
    await call.answer("Заявка отправлена")
