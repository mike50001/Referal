"""Простое хранилище на SQLite: история диалогов и покупки."""
import json

import aiosqlite

from config import DB_PATH, HISTORY_LIMIT

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS messages (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL,
    role      TEXT    NOT NULL,          -- 'user' или 'assistant'
    content   TEXT    NOT NULL,
    created_at TEXT    DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);

CREATE TABLE IF NOT EXISTS purchases (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    product_id    TEXT    NOT NULL,
    stars         INTEGER NOT NULL,
    charge_id     TEXT,                  -- telegram_payment_charge_id (для возвратов)
    created_at    TEXT    DEFAULT (datetime('now'))
);
"""


async def init() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_INIT_SQL)
        await db.commit()


async def add_message(user_id: int, role: str, content: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content),
        )
        await db.commit()


async def get_history(user_id: int, limit: int = HISTORY_LIMIT) -> list[dict]:
    """Последние сообщения в хронологическом порядке для передачи в Claude."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT role, content FROM messages WHERE user_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
    rows.reverse()
    return [{"role": role, "content": content} for role, content in rows]


async def record_purchase(
    user_id: int, product_id: str, stars: int, charge_id: str
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO purchases (user_id, product_id, stars, charge_id) "
            "VALUES (?, ?, ?, ?)",
            (user_id, product_id, stars, charge_id),
        )
        await db.commit()
