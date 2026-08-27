"""Разовое продление подписки ВСЕМ пользователям бота на N дней.

Продлевает срок и в панели Remnawave, и в базе бота (bot.db) — синхронно.
Заодно мигрирует тех, кого ещё нет в Remnawave (создаёт с нужным сроком).

Использование:
    python extend_all.py            # +7 дней (по умолчанию)
    python extend_all.py 30         # +30 дней
"""
import sqlite3
import sys
import time

import config
import database as db
from remna import Remna


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    add_ms = days * 86400 * 1000
    now = int(time.time() * 1000)

    config.validate()
    db.init()
    r = Remna()

    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT user_id, expiry_ms FROM subs WHERE expiry_ms > 0").fetchall()

    ok = 0
    for row in rows:
        uid = row["user_id"]
        base = row["expiry_ms"] or 0
        base = base if base > now else now      # истёкшим считаем от «сейчас»
        new_ms = base + add_ms
        try:
            cid, uname, exp, _link = r.set_expiry(uid, new_ms)
            db.set_sub(uid, cid, uname, exp)
            ok += 1
            print("продлён", uid)
        except Exception as e:
            print("СБОЙ", uid, e)

    print(f"\nГОТОВО: продлено {ok} из {len(rows)} на {days} дней.")


if __name__ == "__main__":
    main()
