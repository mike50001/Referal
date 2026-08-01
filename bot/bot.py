"""VPN-магазин в Telegram: тарифы, ручная оплата, рефералка (% на баланс),
автовыдача ключа через панель 3x-ui.

Запуск: заполни .env (см. .env.example), затем `python bot.py`.
"""
import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import config
import database as db
import texts
import tariffs
from xui import XUI, XUIError

logging.basicConfig(level=logging.INFO)
router = Router()
xui = XUI()


# ---------------- клавиатуры ----------------
def main_menu(uid: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔑 Купить / продлить доступ", callback_data="menu:buy")],
        [InlineKeyboardButton(text="📱 Моя подписка", callback_data="menu:sub")],
        [InlineKeyboardButton(text="📲 Инструкция", callback_data="menu:help")],
        [InlineKeyboardButton(text="🎁 Рефералка", callback_data="menu:ref")],
    ]
    if uid in config.ADMIN_IDS:
        rows.append([InlineKeyboardButton(text="🛠 Админка", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_btn() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:back")]])


def tariffs_kb() -> InlineKeyboardMarkup:
    rows = []
    for key, (name, days, price) in tariffs.TARIFFS.items():
        rows.append([InlineKeyboardButton(
            text=f"{name} — {price} {config.CURRENCY}", callback_data=f"buy:{key}")])
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def fmt_expiry(expiry_ms: int) -> str:
    if not expiry_ms:
        return "—"
    dt = datetime.fromtimestamp(expiry_ms / 1000, tz=timezone.utc)
    return dt.strftime("%d.%m.%Y")


# ---------------- /start ----------------
@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    ref = None
    if command.args and command.args.isdigit():
        ref = int(command.args)
    db.ensure_user(message.from_user.id, message.from_user.username or "",
                   message.from_user.first_name or "", referrer_id=ref)
    await message.answer(texts.WELCOME, reply_markup=main_menu(message.from_user.id))


@router.callback_query(F.data == "menu:back")
async def cb_back(cq: CallbackQuery):
    await cq.message.edit_text(texts.WELCOME, reply_markup=main_menu(cq.from_user.id))
    await cq.answer()


# ---------------- инструкция ----------------
@router.callback_query(F.data == "menu:help")
async def cb_help(cq: CallbackQuery):
    await cq.message.edit_text(texts.HELP_CONNECT, reply_markup=back_btn())
    await cq.answer()


# ---------------- моя подписка ----------------
@router.callback_query(F.data == "menu:sub")
async def cb_sub(cq: CallbackQuery):
    sub = db.get_sub(cq.from_user.id)
    now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    if not sub or not sub["client_uuid"] or (sub["expiry_ms"] and sub["expiry_ms"] < now_ms):
        await cq.message.edit_text(texts.NO_SUB, reply_markup=tariffs_kb())
        await cq.answer()
        return
    try:
        inbound = await xui.get_inbound()
        link = xui._build_link(inbound, sub["client_uuid"], sub["email"])
    except XUIError:
        link = "(не удалось получить ссылку, напиши в поддержку)"
    text = (f"📱 <b>Твоя подписка</b>\n\n"
            f"Активна до: <b>{fmt_expiry(sub['expiry_ms'])}</b>\n\n"
            f"🔗 Ссылка для v2rayTun:\n<code>{link}</code>\n\n"
            f"Как подключиться — кнопка «Инструкция» в меню.")
    await cq.message.edit_text(text, reply_markup=back_btn())
    await cq.answer()


# ---------------- рефералка ----------------
@router.callback_query(F.data == "menu:ref")
async def cb_ref(cq: CallbackQuery):
    u = db.get_user(cq.from_user.id)
    me = await cq.bot.get_me()
    link = f"https://t.me/{me.username}?start={cq.from_user.id}"
    text = texts.REF_INFO.format(
        percent=config.REFERRAL_PERCENT, link=link,
        count=db.referral_count(cq.from_user.id),
        earned=u["ref_earned"], balance=u["balance"], cur=config.CURRENCY)
    await cq.message.edit_text(text, reply_markup=back_btn())
    await cq.answer()


# ---------------- покупка ----------------
@router.callback_query(F.data == "menu:buy")
async def cb_buy(cq: CallbackQuery):
    await cq.message.edit_text("Выбери тариф 👇", reply_markup=tariffs_kb())
    await cq.answer()


@router.callback_query(F.data.startswith("buy:"))
async def cb_pick_tariff(cq: CallbackQuery):
    key = cq.data.split(":", 1)[1]
    t = tariffs.get(key)
    if not t:
        await cq.answer("Тариф не найден", show_alert=True)
        return
    name, days, price = t
    u = db.get_user(cq.from_user.id)
    rows = []
    if u and u["balance"] >= price:
        rows.append([InlineKeyboardButton(
            text=f"💳 Оплатить с баланса ({u['balance']:.0f} {config.CURRENCY})",
            callback_data=f"paybal:{key}")])
    rows.append([InlineKeyboardButton(text="🧾 Оплатить (перевод)",
                                      callback_data=f"payman:{key}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:buy")])
    await cq.message.edit_text(
        f"Тариф: <b>{name}</b>\nЦена: <b>{price} {config.CURRENCY}</b>\n\n"
        f"Как оплатить?", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cq.answer()


async def _provision(bot: Bot, uid: int, key: str, amount: float, credit_ref: bool):
    """Выдаёт/продлевает ключ, обновляет БД, начисляет реферальный %."""
    name, days, price = tariffs.get(key)
    client_uuid, email, expiry_ms, link = await xui.add_or_extend(uid, days)
    db.set_sub(uid, client_uuid, email, expiry_ms)

    if credit_ref:
        u = db.get_user(uid)
        if u and u["referrer_id"]:
            bonus = round(amount * config.REFERRAL_PERCENT / 100, 2)
            if bonus > 0:
                db.add_balance(u["referrer_id"], bonus, as_earning=True)
                try:
                    await bot.send_message(
                        u["referrer_id"],
                        f"🎁 Твой реферал оплатил подписку — тебе начислено "
                        f"<b>{bonus:.0f} {config.CURRENCY}</b> на баланс!")
                except Exception:
                    pass

    await bot.send_message(
        uid,
        f"✅ Доступ активен до <b>{fmt_expiry(expiry_ms)}</b>!\n\n"
        f"🔗 Твоя ссылка:\n<code>{link}</code>\n\n"
        f"Открой v2rayTun → «+» → «Импорт из буфера обмена». "
        f"Подробнее — «Инструкция» в меню.",
        reply_markup=main_menu(uid))


# оплата с баланса — мгновенно
@router.callback_query(F.data.startswith("paybal:"))
async def cb_pay_balance(cq: CallbackQuery):
    key = cq.data.split(":", 1)[1]
    t = tariffs.get(key)
    if not t:
        await cq.answer("Тариф не найден", show_alert=True)
        return
    name, days, price = t
    if not db.spend_balance(cq.from_user.id, price):
        await cq.answer("Недостаточно средств на балансе", show_alert=True)
        return
    await cq.answer("Оплачено с баланса ✅")
    try:
        await _provision(cq.bot, cq.from_user.id, key, price, credit_ref=False)
        await cq.message.delete()
    except XUIError as e:
        db.add_balance(cq.from_user.id, price)  # вернуть деньги при сбое
        await cq.message.edit_text(f"⚠️ Ошибка выдачи ключа: {e}\nСредства возвращены на баланс.",
                                   reply_markup=back_btn())


# ручная оплата — заявка админу
@router.callback_query(F.data.startswith("payman:"))
async def cb_pay_manual(cq: CallbackQuery):
    key = cq.data.split(":", 1)[1]
    t = tariffs.get(key)
    if not t:
        await cq.answer("Тариф не найден", show_alert=True)
        return
    name, days, price = t
    text = texts.PAY_INSTRUCTIONS.format(
        name=name, price=price, cur=config.CURRENCY, details=config.PAYMENT_DETAILS)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid:{key}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:buy")]])
    await cq.message.edit_text(text, reply_markup=kb)
    await cq.answer()


@router.callback_query(F.data.startswith("paid:"))
async def cb_paid(cq: CallbackQuery):
    key = cq.data.split(":", 1)[1]
    t = tariffs.get(key)
    if not t:
        await cq.answer("Тариф не найден", show_alert=True)
        return
    name, days, price = t
    pid = db.create_payment(cq.from_user.id, key, price)
    await cq.message.edit_text(texts.PAY_SENT, reply_markup=back_btn())
    await cq.answer()
    uname = f"@{cq.from_user.username}" if cq.from_user.username else cq.from_user.first_name
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm:{pid}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{pid}")]])
    for admin in config.ADMIN_IDS:
        try:
            await cq.bot.send_message(
                admin,
                f"🧾 <b>Новая заявка на оплату #{pid}</b>\n"
                f"Пользователь: {uname} (<code>{cq.from_user.id}</code>)\n"
                f"Тариф: {name} — {price} {config.CURRENCY}\n\n"
                f"Проверь поступление и подтверди/отклони.",
                reply_markup=admin_kb)
        except Exception:
            pass


# ---------------- админ: подтверждение ----------------
@router.callback_query(F.data.startswith(("confirm:", "reject:")))
async def cb_decide(cq: CallbackQuery):
    if cq.from_user.id not in config.ADMIN_IDS:
        await cq.answer("Нет прав", show_alert=True)
        return
    action, pid = cq.data.split(":")
    pid = int(pid)
    pay = db.get_payment(pid)
    if not pay:
        await cq.answer("Заявка не найдена", show_alert=True)
        return
    if pay["status"] != "pending":
        await cq.answer(f"Уже обработана: {pay['status']}", show_alert=True)
        return

    if action == "reject":
        db.set_payment_status(pid, "rejected")
        await cq.message.edit_text(cq.message.html_text + "\n\n❌ Отклонено")
        try:
            await cq.bot.send_message(pay["user_id"],
                                      "❌ Оплата не подтверждена. Если ты платил — напиши в поддержку.")
        except Exception:
            pass
        await cq.answer("Отклонено")
        return

    # confirm
    try:
        await _provision(cq.bot, pay["user_id"], pay["tariff_key"], pay["amount"],
                         credit_ref=True)
        db.set_payment_status(pid, "confirmed")
        await cq.message.edit_text(cq.message.html_text + "\n\n✅ Подтверждено, ключ выдан")
        await cq.answer("Подтверждено ✅")
    except XUIError as e:
        await cq.answer(f"Ошибка панели: {e}", show_alert=True)


# ---------------- админка ----------------
@router.callback_query(F.data == "menu:admin")
async def cb_admin(cq: CallbackQuery):
    if cq.from_user.id not in config.ADMIN_IDS:
        await cq.answer("Нет прав", show_alert=True)
        return
    users, active, revenue = db.stats()
    await cq.message.edit_text(
        f"🛠 <b>Статистика</b>\n\n"
        f"👥 Пользователей: <b>{users}</b>\n"
        f"✅ Активных подписок: <b>{active}</b>\n"
        f"💰 Выручка (подтверждённая): <b>{revenue:.0f} {config.CURRENCY}</b>",
        reply_markup=back_btn())
    await cq.answer()


@router.message(Command("id"))
async def cmd_id(message: Message):
    await message.answer(f"Твой Telegram id: <code>{message.from_user.id}</code>")


# ---------------- запуск ----------------
async def main():
    config.validate()
    db.init()
    bot = Bot(token=config.BOT_TOKEN,
              default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await xui.close()


if __name__ == "__main__":
    asyncio.run(main())
