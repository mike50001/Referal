"""Трекинг пользователей/событий и команды /stats, /myid."""

from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from .. import stats
from ..content import SECTIONS, find_key_by_label

# admin_id прокидывается из main при регистрации.
_admin_id = 0


def _section_label(event: str) -> str:
    """section:key -> подпись раздела."""
    key = event.split(":", 1)[1] if ":" in event else event
    item = SECTIONS.get(key)
    return item[0] if item else key


async def track(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Группа -1: срабатывает на каждое обновление, пишет пользователя/событие.

    Любые ошибки трекинга проглатываются — статистика не должна ломать бота.
    """
    if not stats.enabled():
        return
    try:
        user = update.effective_user
        await stats.track_user(user)
        uid = user.id if user else None

        if update.callback_query and update.callback_query.data:
            await stats.track_event(uid, "cb:" + update.callback_query.data)
            return

        msg = update.message
        if msg and msg.text:
            text = msg.text.strip()
            if text.startswith("/start"):
                await stats.track_event(uid, "start")
            else:
                key = find_key_by_label(text)
                if key:
                    await stats.track_event(uid, "section:" + key)
    except Exception:  # noqa: BLE001
        pass


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if _admin_id and (not user or user.id != _admin_id):
        return  # чужим не отвечаем
    if not stats.enabled():
        await update.message.reply_text(
            "📊 Статистика не подключена.\n"
            "Добавьте в Railway плагин Postgres — переменная DATABASE_URL "
            "появится автоматически, и статистика заработает."
        )
        return

    s = await stats.get_stats()
    lines = [
        "📊 <b>Статистика бота</b>\n",
        f"👥 Всего пользователей: <b>{s['total']}</b>",
        f"🆕 Новых за 24ч: <b>{s['new_24h']}</b>",
        f"🆕 Новых за 7 дней: <b>{s['new_7d']}</b>",
        f"⚡️ Активных за 24ч: <b>{s['active_24h']}</b>",
        f"🚀 Запусков /start: <b>{s['starts']}</b>",
    ]
    if s["top_sections"]:
        lines.append("\n<b>🔝 Популярные разделы:</b>")
        for event, count in s["top_sections"]:
            lines.append(f"• {_section_label(event)} — {count}")
    await update.message.reply_html("\n".join(lines))


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    await update.message.reply_html(
        f"Ваш Telegram ID: <code>{user.id}</code>\n\n"
        "Впишите его в переменную <b>ADMIN_ID</b> на Railway, чтобы "
        "команда /stats была доступна только вам."
    )


def register(app: Application, admin_id: int = 0) -> None:
    global _admin_id
    _admin_id = admin_id
    # Трекинг — в группе -1, раньше всех остальных обработчиков.
    app.add_handler(TypeHandler(Update, track), group=-1)
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("myid", myid_command))
