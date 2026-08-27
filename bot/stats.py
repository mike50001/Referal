"""Учёт пользователей и статистика (Postgres, опционально).

Если DATABASE_URL не задан — все функции становятся no-op, бот работает
как обычно, только без статистики.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_pool = None  # asyncpg.Pool | None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id    BIGINT PRIMARY KEY,
    username   TEXT,
    first_name TEXT,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS events (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT,
    event      TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_event ON events (event);
CREATE INDEX IF NOT EXISTS idx_events_created ON events (created_at);
"""


def enabled() -> bool:
    return _pool is not None


async def init(database_url: str) -> None:
    """Подключиться к Postgres и создать таблицы. Без URL — тихо пропустить."""
    global _pool
    if not database_url:
        logger.info("Статистика выключена: DATABASE_URL не задан.")
        return
    try:
        import asyncpg
    except ImportError:
        logger.warning("asyncpg не установлен — статистика недоступна.")
        return
    try:
        _pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
        async with _pool.acquire() as conn:
            await conn.execute(_SCHEMA)
        logger.info("Статистика подключена (Postgres).")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не удалось подключить статистику: %s", exc)
        _pool = None


async def close() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def track_user(user) -> None:
    if _pool is None or user is None:
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (user_id, username, first_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE
                SET username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_seen = now()
                """,
                user.id, user.username, user.first_name,
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("track_user error: %s", exc)


async def track_event(user_id: int | None, event: str) -> None:
    if _pool is None:
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO events (user_id, event) VALUES ($1, $2)",
                user_id, event,
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("track_event error: %s", exc)


async def get_stats() -> dict:
    """Собрать сводку для /stats."""
    if _pool is None:
        return {}
    async with _pool.acquire() as conn:
        total = await conn.fetchval("SELECT count(*) FROM users")
        new_24h = await conn.fetchval(
            "SELECT count(*) FROM users WHERE first_seen >= now() - interval '24 hours'"
        )
        new_7d = await conn.fetchval(
            "SELECT count(*) FROM users WHERE first_seen >= now() - interval '7 days'"
        )
        active_24h = await conn.fetchval(
            "SELECT count(DISTINCT user_id) FROM events "
            "WHERE created_at >= now() - interval '24 hours'"
        )
        starts = await conn.fetchval(
            "SELECT count(*) FROM events WHERE event = 'start'"
        )
        top = await conn.fetch(
            "SELECT event, count(*) AS c FROM events "
            "WHERE event LIKE 'section:%' "
            "GROUP BY event ORDER BY c DESC LIMIT 10"
        )
    return {
        "total": total or 0,
        "new_24h": new_24h or 0,
        "new_7d": new_7d or 0,
        "active_24h": active_24h or 0,
        "starts": starts or 0,
        "top_sections": [(r["event"], r["c"]) for r in top],
    }
