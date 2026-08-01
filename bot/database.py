"""Простая БД на sqlite3 (stdlib). Для небольшого бота этого достаточно."""
import sqlite3
import time
from contextlib import contextmanager

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY,
    username      TEXT,
    first_name    TEXT,
    balance       REAL    DEFAULT 0,
    ref_earned    REAL    DEFAULT 0,
    referrer_id   INTEGER,
    trial_claimed INTEGER DEFAULT 0,
    created_at    INTEGER
);
CREATE TABLE IF NOT EXISTS subs (
    user_id     INTEGER PRIMARY KEY,
    client_uuid TEXT,
    email       TEXT,
    expiry_ms   INTEGER DEFAULT 0,
    warned      INTEGER DEFAULT 0
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
        # миграции для БД, созданных старой версией
        sub_cols = [r["name"] for r in con.execute("PRAGMA table_info(subs)")]
        if "warned" not in sub_cols:
            con.execute("ALTER TABLE subs ADD COLUMN warned INTEGER DEFAULT 0")
        user_cols = [r["name"] for r in con.execute("PRAGMA table_info(users)")]
        if "trial_claimed" not in user_cols:
            con.execute("ALTER TABLE users ADD COLUMN trial_claimed INTEGER DEFAULT 0")


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


def is_trial_claimed(uid: int) -> bool:
    with _conn() as con:
        row = con.execute("SELECT trial_claimed FROM users WHERE user_id=?", (uid,)).fetchone()
        return bool(row and row["trial_claimed"])


def set_trial_claimed(uid: int):
    with _conn() as con:
        con.execute("UPDATE users SET trial_claimed=1 WHERE user_id=?", (uid,))


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
        # warned=0 — при продлении снова разрешаем предупреждение об окончании
        con.execute(
            "INSERT INTO subs(user_id, client_uuid, email, expiry_ms, warned) VALUES(?,?,?,?,0) "
            "ON CONFLICT(user_id) DO UPDATE SET client_uuid=excluded.client_uuid, "
            "email=excluded.email, expiry_ms=excluded.expiry_ms, warned=0",
            (uid, client_uuid, email, expiry_ms))


def subs_expiring(now_ms: int, until_ms: int):
    """Активные подписки, которые заканчиваются в промежутке (сейчас; until],
    и по которым ещё не слали предупреждение."""
    with _conn() as con:
        return con.execute(
            "SELECT * FROM subs WHERE expiry_ms>? AND expiry_ms<=? AND warned=0",
            (now_ms, until_ms)).fetchall()


def mark_warned(uid: int):
    with _conn() as con:
        con.execute("UPDATE subs SET warned=1 WHERE user_id=?", (uid,))


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
