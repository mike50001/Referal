"""VPN-магазин в Telegram: тарифы, ручная оплата, рефералка (% на баланс),
автовыдача ключа через панель 3x-ui.

На pyTelegramBotAPI (чистый Python, без компилируемых зависимостей).
Запуск: заполни .env (см. .env.example), затем `python bot.py`.
"""
import logging
import threading
import time
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


def admin_link():
    """Ссылка на страницу администратора в Telegram (из ADMIN_CONTACT)."""
    c = config.ADMIN_CONTACT.strip()
    if not c:
        return None
    if c.startswith("http"):
        return c
    return "https://t.me/" + c.lstrip("@")


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
    uid = message.from_user.id
    is_new = db.ensure_user(uid, message.from_user.username or "",
                            message.from_user.first_name or "", referrer_id=ref)
    note = ""
    if is_new:
        u = db.get_user(uid)
        if u["referrer_id"]:
            _grant_referral(uid, u["referrer_id"])
            note = texts.TRIAL_NOTE.format(days=config.REFERRAL_DAYS)
    bot.send_message(message.chat.id, texts.WELCOME + note, reply_markup=main_menu(uid))


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
    count = db.referral_count(call.from_user.id)
    link = f"https://t.me/{bot.get_me().username}?start={call.from_user.id}"
    text = texts.REF_INFO.format(days=config.REFERRAL_DAYS, link=link,
                                 count=count, earned_days=count * config.REFERRAL_DAYS)
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


def grant_days(uid: int, days: int):
    """Создаёт/продлевает ключ на N дней, обновляет БД. Возвращает (expiry_ms, link)."""
    client_uuid, email, expiry_ms, link = xui.add_or_extend(uid, days)
    db.set_sub(uid, client_uuid, email, expiry_ms)
    return expiry_ms, link


def _grant_referral(new_uid: int, referrer_id: int):
    """Пробные дни новому пользователю и бонусные дни пригласившему."""
    days = config.REFERRAL_DAYS
    try:
        grant_days(new_uid, days)
    except XUIError as e:
        logging.warning("trial provision failed: %s", e)
    try:
        expiry, _ = grant_days(referrer_id, days)
        bot.send_message(referrer_id,
                         f"🎁 По твоей ссылке присоединился друг — тебе <b>+{days} дней</b>! "
                         f"Доступ активен до <b>{fmt_expiry(expiry)}</b>.")
    except Exception as e:
        logging.warning("referrer bonus failed: %s", e)


def provision(uid: int, key: str):
    """Выдаёт/продлевает ключ по купленному тарифу и шлёт пользователю ссылку."""
    name, days, price = tariffs.get(key)
    expiry_ms, link = grant_days(uid, days)
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
        provision(call.from_user.id, key)
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
    text = texts.PAY_INSTRUCTIONS.format(name=name, price=price, cur=config.CURRENCY)
    kb = types.InlineKeyboardMarkup()
    link = admin_link()
    if link:
        kb.add(types.InlineKeyboardButton("✍️ Написать администратору", url=link))
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
        provision(pay["user_id"], pay["tariff_key"])
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


# ---------------- уведомления об окончании подписки ----------------
def check_expiry():
    now = now_ms()
    until = now + config.EXPIRY_WARN_DAYS * 86400 * 1000
    for row in db.subs_expiring(now, until):
        try:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🔑 Продлить доступ", callback_data="menu:buy"))
            bot.send_message(row["user_id"],
                             texts.EXPIRY_WARN.format(date=fmt_expiry(row["expiry_ms"])),
                             reply_markup=kb)
            db.mark_warned(row["user_id"])
        except Exception as e:
            logging.warning("expiry notify %s: %s", row["user_id"], e)


def expiry_watcher():
    while True:
        try:
            check_expiry()
        except Exception as e:
            logging.warning("expiry watcher: %s", e)
        time.sleep(6 * 3600)   # проверяем каждые 6 часов


if __name__ == "__main__":
    logging.info("Bot started")
    threading.Thread(target=expiry_watcher, daemon=True).start()
    bot.infinity_polling(skip_pending=True)
