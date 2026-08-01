"""VPN-магазин в Telegram: тарифы, ручная оплата, рефералка (% на баланс),
автовыдача ключа через панель 3x-ui.

На pyTelegramBotAPI (чистый Python, без компилируемых зависимостей).
Запуск: заполни .env (см. .env.example), затем `python bot.py`.
"""
import logging
from datetime import datetime, timezone

import telebot
from telebot import types

import config
import database as db
import tariffs
import texts
from xui import XUI, XUIError

logging.basicConfig(level=logging.INFO)

config.validate()
db.init()
bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode="HTML")
xui = XUI()


# ---------------- клавиатуры ----------------
def main_menu(uid: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔑 Купить / продлить доступ", callback_data="menu:buy"))
    kb.add(types.InlineKeyboardButton("📱 Моя подписка", callback_data="menu:sub"))
    kb.add(types.InlineKeyboardButton("📲 Инструкция", callback_data="menu:help"))
    kb.add(types.InlineKeyboardButton("🎁 Рефералка", callback_data="menu:ref"))
    if uid in config.ADMIN_IDS:
        kb.add(types.InlineKeyboardButton("🛠 Админка", callback_data="menu:admin"))
    return kb


def back_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⬅️ В меню", callback_data="menu:back"))
    return kb


def tariffs_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    for key, (name, days, price) in tariffs.TARIFFS.items():
        kb.add(types.InlineKeyboardButton(
            f"{name} — {price} {config.CURRENCY}", callback_data=f"buy:{key}"))
    kb.add(types.InlineKeyboardButton("⬅️ В меню", callback_data="menu:back"))
    return kb


def fmt_expiry(expiry_ms: int) -> str:
    if not expiry_ms:
        return "—"
    return datetime.fromtimestamp(expiry_ms / 1000, tz=timezone.utc).strftime("%d.%m.%Y")


def now_ms() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)


def edit(call, text, kb=None):
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                          reply_markup=kb, disable_web_page_preview=True)


# ---------------- /start ----------------
@bot.message_handler(commands=["start"])
def cmd_start(message):
    ref = None
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1 and parts[1].strip().isdigit():
        ref = int(parts[1].strip())
    db.ensure_user(message.from_user.id, message.from_user.username or "",
                   message.from_user.first_name or "", referrer_id=ref)
    bot.send_message(message.chat.id, texts.WELCOME,
                     reply_markup=main_menu(message.from_user.id))


@bot.message_handler(commands=["id"])
def cmd_id(message):
    bot.send_message(message.chat.id, f"Твой Telegram id: <code>{message.from_user.id}</code>")


# ---------------- меню ----------------
@bot.callback_query_handler(func=lambda c: c.data == "menu:back")
def cb_back(call):
    edit(call, texts.WELCOME, main_menu(call.from_user.id))
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data == "menu:help")
def cb_help(call):
    edit(call, texts.HELP_CONNECT, back_kb())
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data == "menu:sub")
def cb_sub(call):
    sub = db.get_sub(call.from_user.id)
    if not sub or not sub["client_uuid"] or (sub["expiry_ms"] and sub["expiry_ms"] < now_ms()):
        edit(call, texts.NO_SUB, tariffs_kb())
        bot.answer_callback_query(call.id)
        return
    try:
        inbound = xui.get_inbound()
        link = xui.build_link(inbound, sub["client_uuid"], sub["email"])
    except XUIError:
        link = "(не удалось получить ссылку, напиши в поддержку)"
    text = (f"📱 <b>Твоя подписка</b>\n\n"
            f"Активна до: <b>{fmt_expiry(sub['expiry_ms'])}</b>\n\n"
            f"🔗 Ссылка для v2rayTun:\n<code>{link}</code>\n\n"
            f"Как подключиться — кнопка «Инструкция» в меню.")
    edit(call, text, back_kb())
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data == "menu:ref")
def cb_ref(call):
    u = db.get_user(call.from_user.id)
    link = f"https://t.me/{bot.get_me().username}?start={call.from_user.id}"
    text = texts.REF_INFO.format(
        percent=config.REFERRAL_PERCENT, link=link,
        count=db.referral_count(call.from_user.id),
        earned=u["ref_earned"], balance=u["balance"], cur=config.CURRENCY)
    edit(call, text, back_kb())
    bot.answer_callback_query(call.id)


# ---------------- покупка ----------------
@bot.callback_query_handler(func=lambda c: c.data == "menu:buy")
def cb_buy(call):
    edit(call, "Выбери тариф 👇", tariffs_kb())
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("buy:"))
def cb_pick_tariff(call):
    key = call.data.split(":", 1)[1]
    t = tariffs.get(key)
    if not t:
        bot.answer_callback_query(call.id, "Тариф не найден", show_alert=True)
        return
    name, days, price = t
    u = db.get_user(call.from_user.id)
    kb = types.InlineKeyboardMarkup()
    if u and u["balance"] >= price:
        kb.add(types.InlineKeyboardButton(
            f"💳 Оплатить с баланса ({u['balance']:.0f} {config.CURRENCY})",
            callback_data=f"paybal:{key}"))
    kb.add(types.InlineKeyboardButton("🧾 Оплатить (перевод)", callback_data=f"payman:{key}"))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu:buy"))
    edit(call, f"Тариф: <b>{name}</b>\nЦена: <b>{price} {config.CURRENCY}</b>\n\nКак оплатить?", kb)
    bot.answer_callback_query(call.id)


def provision(uid: int, key: str, amount: float, credit_ref: bool):
    """Выдаёт/продлевает ключ, обновляет БД, начисляет реферальный %."""
    name, days, price = tariffs.get(key)
    client_uuid, email, expiry_ms, link = xui.add_or_extend(uid, days)
    db.set_sub(uid, client_uuid, email, expiry_ms)

    if credit_ref:
        u = db.get_user(uid)
        if u and u["referrer_id"]:
            bonus = round(amount * config.REFERRAL_PERCENT / 100, 2)
            if bonus > 0:
                db.add_balance(u["referrer_id"], bonus, as_earning=True)
                try:
                    bot.send_message(u["referrer_id"],
                                     f"🎁 Твой реферал оплатил подписку — тебе начислено "
                                     f"<b>{bonus:.0f} {config.CURRENCY}</b> на баланс!")
                except Exception:
                    pass

    bot.send_message(
        uid,
        f"✅ Доступ активен до <b>{fmt_expiry(expiry_ms)}</b>!\n\n"
        f"🔗 Твоя ссылка:\n<code>{link}</code>\n\n"
        f"Открой v2rayTun → «+» → «Импорт из буфера обмена». "
        f"Подробнее — «Инструкция» в меню.",
        reply_markup=main_menu(uid), disable_web_page_preview=True)


@bot.callback_query_handler(func=lambda c: c.data.startswith("paybal:"))
def cb_pay_balance(call):
    key = call.data.split(":", 1)[1]
    t = tariffs.get(key)
    if not t:
        bot.answer_callback_query(call.id, "Тариф не найден", show_alert=True)
        return
    name, days, price = t
    if not db.spend_balance(call.from_user.id, price):
        bot.answer_callback_query(call.id, "Недостаточно средств на балансе", show_alert=True)
        return
    bot.answer_callback_query(call.id, "Оплачено с баланса ✅")
    try:
        provision(call.from_user.id, key, price, credit_ref=False)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except XUIError as e:
        db.add_balance(call.from_user.id, price)  # вернуть деньги при сбое
        edit(call, f"⚠️ Ошибка выдачи ключа: {e}\nСредства возвращены на баланс.", back_kb())


@bot.callback_query_handler(func=lambda c: c.data.startswith("payman:"))
def cb_pay_manual(call):
    key = call.data.split(":", 1)[1]
    t = tariffs.get(key)
    if not t:
        bot.answer_callback_query(call.id, "Тариф не найден", show_alert=True)
        return
    name, days, price = t
    text = texts.PAY_INSTRUCTIONS.format(
        name=name, price=price, cur=config.CURRENCY, details=config.PAYMENT_DETAILS)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Я оплатил", callback_data=f"paid:{key}"))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu:buy"))
    edit(call, text, kb)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("paid:"))
def cb_paid(call):
    key = call.data.split(":", 1)[1]
    t = tariffs.get(key)
    if not t:
        bot.answer_callback_query(call.id, "Тариф не найден", show_alert=True)
        return
    name, days, price = t
    pid = db.create_payment(call.from_user.id, key, price)
    edit(call, texts.PAY_SENT, back_kb())
    bot.answer_callback_query(call.id)
    uname = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm:{pid}"),
           types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{pid}"))
    for admin in config.ADMIN_IDS:
        try:
            bot.send_message(
                admin,
                f"🧾 <b>Новая заявка на оплату #{pid}</b>\n"
                f"Пользователь: {uname} (<code>{call.from_user.id}</code>)\n"
                f"Тариф: {name} — {price} {config.CURRENCY}\n\n"
                f"Проверь поступление и подтверди/отклони.",
                reply_markup=kb)
        except Exception:
            pass


# ---------------- админ: подтверждение ----------------
@bot.callback_query_handler(func=lambda c: c.data.startswith(("confirm:", "reject:")))
def cb_decide(call):
    if call.from_user.id not in config.ADMIN_IDS:
        bot.answer_callback_query(call.id, "Нет прав", show_alert=True)
        return
    action, pid = call.data.split(":")
    pid = int(pid)
    pay = db.get_payment(pid)
    if not pay:
        bot.answer_callback_query(call.id, "Заявка не найдена", show_alert=True)
        return
    if pay["status"] != "pending":
        bot.answer_callback_query(call.id, f"Уже обработана: {pay['status']}", show_alert=True)
        return

    if action == "reject":
        db.set_payment_status(pid, "rejected")
        edit(call, f"Заявка #{pid}: ❌ отклонена")
        try:
            bot.send_message(pay["user_id"],
                             "❌ Оплата не подтверждена. Если ты платил — напиши в поддержку.")
        except Exception:
            pass
        bot.answer_callback_query(call.id, "Отклонено")
        return

    try:
        provision(pay["user_id"], pay["tariff_key"], pay["amount"], credit_ref=True)
        db.set_payment_status(pid, "confirmed")
        edit(call, f"Заявка #{pid}: ✅ подтверждена, ключ выдан")
        bot.answer_callback_query(call.id, "Подтверждено ✅")
    except XUIError as e:
        bot.answer_callback_query(call.id, f"Ошибка панели: {e}", show_alert=True)


# ---------------- админка ----------------
@bot.callback_query_handler(func=lambda c: c.data == "menu:admin")
def cb_admin(call):
    if call.from_user.id not in config.ADMIN_IDS:
        bot.answer_callback_query(call.id, "Нет прав", show_alert=True)
        return
    users, active, revenue = db.stats()
    edit(call,
         f"🛠 <b>Статистика</b>\n\n"
         f"👥 Пользователей: <b>{users}</b>\n"
         f"✅ Активных подписок: <b>{active}</b>\n"
         f"💰 Выручка (подтверждённая): <b>{revenue:.0f} {config.CURRENCY}</b>",
         back_kb())
    bot.answer_callback_query(call.id)


if __name__ == "__main__":
    logging.info("Bot started")
    bot.infinity_polling(skip_pending=True)
