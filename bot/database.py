"""Простая БД на sqlite3 (stdlib). Для небольшого бота этого достаточно."""
import sqlite3
import time
from contextlib import contextmanager

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    balance     REAL    DEFAULT 0,
    ref_earned  REAL    DEFAULT 0,
    referrer_id INTEGER,
    created_at  INTEGER
);
CREATE TABLE IF NOT EXISTS subs (
    user_id     INTEGER PRIMARY KEY,
    client_uuid TEXT,
    email       TEXT,
    expiry_ms   INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS payments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    tariff_key  TEXT,
    amount      REAL,
    status      TEXT    DEFAULT 'pending',   -- pending | confirmed | rejected
    created_at  INTEGER,
    decided_at  INTEGER
);
"""


@contextmanager
def _conn():
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init() -> None:
    with _conn() as con:
        con.executescript(_SCHEMA)


# ---------- users ----------
def get_user(uid: int):
    with _conn() as con:
        return con.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()


def ensure_user(uid: int, username: str, first_name: str, referrer_id=None):
    """Создаёт пользователя, если его нет. Реферер ставится только при первом заходе
    и только если это не сам пользователь."""
    with _conn() as con:
        row = con.execute("SELECT user_id FROM users WHERE user_id=?", (uid,)).fetchone()
        if row:
            con.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?",
                        (username, first_name, uid))
            return False
        if referrer_id == uid:
            referrer_id = None
        con.execute(
            "INSERT INTO users(user_id, username, first_name, referrer_id, created_at) "
            "VALUES(?,?,?,?,?)",
            (uid, username, first_name, referrer_id, int(time.time())))
        return True


def add_balance(uid: int, amount: float, as_earning: bool = False):
    with _conn() as con:
        if as_earning:
            con.execute("UPDATE users SET balance=balance+?, ref_earned=ref_earned+? "
                        "WHERE user_id=?", (amount, amount, uid))
        else:
            con.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid))


def spend_balance(uid: int, amount: float) -> bool:
    with _conn() as con:
        row = con.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
        if not row or row["balance"] < amount:
            return False
        con.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, uid))
        return True


def referral_count(uid: int) -> int:
    with _conn() as con:
        return con.execute("SELECT COUNT(*) c FROM users WHERE referrer_id=?",
                           (uid,)).fetchone()["c"]


# ---------- subs ----------
def get_sub(uid: int):
    with _conn() as con:
        return con.execute("SELECT * FROM subs WHERE user_id=?", (uid,)).fetchone()


def set_sub(uid: int, client_uuid: str, email: str, expiry_ms: int):
    with _conn() as con:
        con.execute(
            "INSERT INTO subs(user_id, client_uuid, email, expiry_ms) VALUES(?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET client_uuid=excluded.client_uuid, "
            "email=excluded.email, expiry_ms=excluded.expiry_ms",
            (uid, client_uuid, email, expiry_ms))


# ---------- payments ----------
def create_payment(uid: int, tariff_key: str, amount: float) -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO payments(user_id, tariff_key, amount, created_at) VALUES(?,?,?,?)",
            (uid, tariff_key, amount, int(time.time())))
        return cur.lastrowid


def get_payment(pid: int):
    with _conn() as con:
        return con.execute("SELECT * FROM payments WHERE id=?", (pid,)).fetchone()


def set_payment_status(pid: int, status: str):
    with _conn() as con:
        con.execute("UPDATE payments SET status=?, decided_at=? WHERE id=?",
                    (status, int(time.time()), pid))


def stats():
    with _conn() as con:
        users = con.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        active = con.execute("SELECT COUNT(*) c FROM subs WHERE expiry_ms>?",
                             (int(time.time() * 1000),)).fetchone()["c"]
        revenue = con.execute(
            "SELECT COALESCE(SUM(amount),0) s FROM payments WHERE status='confirmed'"
        ).fetchone()["s"]
        return users, active, revenue
