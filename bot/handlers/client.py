"""Хендлеры клиентской части: приветствие и сбор заявки на обмен."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import rates
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
    "Добро пожаловать в 💱 <b>Misha Cash</b>!\n\n"
    "⚡ Быстрый обмен\n"
    "💵 Выгодные курсы\n"
    "🔒 Безопасные сделки\n"
    "🤝 Поддержка на каждом этапе\n\n"
    "━━━━━━━━━━━━━━\n\n"
    "⚠️ <b>Остерегайтесь мошенников!</b>\n\n"
    "❌ Не переводите средства по реквизитам, полученным не в этом боте.\n"
    "❌ Мы не меняем реквизиты во время сделки.\n"
    "❌ Мы не пишем с других аккаунтов.\n\n"
    "✅ Общайтесь только через официальный бот Misha Cash.\n\n"
    "📩 Если возникли вопросы — обращайтесь в поддержку.\n\n"
    "Спасибо за доверие! 💙\n"
    "Misha Cash 🚀\n\n"
    "👇 Выберите действие ниже."
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


@router.message(F.text == "📈 Узнать курс")
@router.message(Command("rate"))
async def show_rate(message: Message) -> None:
    await message.answer(await rates.client_rates_text())


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

    # Сохраняем как введено (для показа) и числом (для расчёта курса).
    await state.update_data(amount=message.text.strip(), amount_value=value)
    await state.set_state(ExchangeForm.contact)
    await message.answer(
        "Шаг 5/5. Как с вами связаться?\n"
        "Отправьте номер телефона кнопкой ниже или напишите контакт "
        "(телефон / @username) вручную.",
        reply_markup=contact_keyboard(),
    )


# --- Шаг 4: контакт -------------------------------------------------------


@router.message(ExchangeForm.contact, F.contact)
async def contact_shared(message: Message, state: FSMContext, config: Config) -> None:
    await state.update_data(contact=message.contact.phone_number)
    await _show_summary(message, state, config)


@router.message(ExchangeForm.contact, F.text)
async def contact_typed(message: Message, state: FSMContext, config: Config) -> None:
    await state.update_data(contact=message.text.strip())
    await _show_summary(message, state, config)


def _amount_lines(data: dict) -> str:
    """Строки о сумме с учётом выбранного способа и рассчитанного курса."""
    give, get, amount = data.get("give"), data.get("get"), data.get("amount")
    counter = data.get("est_counter")
    if data.get("side") == "get":
        pay = (
            f"≈ <b>{rates.fmt(counter)} {give}</b>"
            if counter is not None
            else f"<b>{give}</b> <i>(сумму рассчитает менеджер)</i>"
        )
        return f"💸 Отдаёте: {pay}\n🎯 Хотите получить: <b>{amount} {get}</b>"
    receive = (
        f"≈ <b>{rates.fmt(counter)} {get}</b>"
        if counter is not None
        else f"<b>{get}</b> <i>(сумму рассчитает менеджер)</i>"
    )
    return f"💸 Отдаёте: <b>{amount} {give}</b>\n💰 Получаете: {receive}"


def _rate_line(data: dict) -> str:
    """Строка с текущим курсом, если он рассчитан."""
    rate = data.get("est_rate")
    if rate is None:
        return ""
    return f"📈 Курс: 1 {data.get('give')} ≈ {rates.fmt(rate)} {data.get('get')}\n"


async def _show_summary(message: Message, state: FSMContext, config: Config) -> None:
    data = await state.get_data()

    # Рассчитываем недостающую сторону по актуальному курсу (если API доступен).
    est = await rates.calculate(
        data.get("give"),
        data.get("get"),
        data.get("amount_value"),
        data.get("side", "give"),
        config.markup_percent,
    )
    if est:
        await state.update_data(est_counter=est["counter"], est_rate=est["rate"])
        data = await state.get_data()

    note = (
        "<i>Курс ориентировочный, точную сумму подтвердит менеджер.</i>\n\n"
        if data.get("est_rate") is not None
        else ""
    )
    text = (
        "Проверьте заявку:\n\n"
        f"{_amount_lines(data)}\n"
        f"{_rate_line(data)}"
        f"📞 Контакт: <b>{data.get('contact')}</b>\n\n"
        f"{note}"
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
        f"{_rate_line(data)}"
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
