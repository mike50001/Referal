"""Клиент к API панели Remnawave (v3). Синхронный (httpx.Client).

Умеет: создать/продлить пользователя, получить ссылку-подписку, включить/
выключить, удалить. Пользователь в Remnawave = username вида tg<telegram_id>.
Ключи выдаются как ссылка-подписка (subscriptionUrl), в которой сразу все
локации (ноды), привязанные к сквадам пользователя.

Авторизация — Bearer-токен (создаётся в панели: Настройки → API токены).
Все запросы идут на {REMNA_BASE_URL}/api/... По умолчанию ответы Remnawave
завёрнуты в {"response": {...}}.

Если у тебя другая версия панели и что-то не так — правки в основном тут.
"""
import time
from datetime import datetime, timezone

import httpx

import config


class RemnaError(Exception):
    pass


def _to_ms(iso: str) -> int:
    """ISO-8601 (в т.ч. с 'Z') -> unix ms."""
    if not iso:
        return 0
    s = iso.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _to_iso(ms: int) -> str:
    """unix ms -> ISO-8601 с миллисекундами и 'Z' (как ждёт Remnawave)."""
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


class Remna:
    def __init__(self):
        self.base = config.REMNA_BASE_URL.rstrip("/")
        self.squad = config.REMNA_SQUAD_UUID
        self._client = httpx.Client(
            timeout=25,
            headers={
                "Authorization": f"Bearer {config.REMNA_TOKEN}",
                "Content-Type": "application/json",
                # Некоторые сборки за Caddy проверяют эти заголовки.
                "X-Forwarded-For": "127.0.0.1",
                "X-Forwarded-Proto": "https",
            },
        )

    # ---------- низкоуровневое ----------
    def _req(self, method: str, path: str, json=None, allow_404=False):
        r = self._client.request(method, f"{self.base}/api{path}", json=json)
        if allow_404 and r.status_code == 404:
            return None
        if not (200 <= r.status_code < 300):
            raise RemnaError(f"{method} {path}: HTTP {r.status_code} {r.text[:300]}")
        if not r.content:
            return {}
        data = r.json()
        return data.get("response", data)

    # ---------- пользователи ----------
    def get_user(self, user_id: int):
        """Возвращает объект пользователя Remnawave или None, если его нет."""
        username = f"tg{user_id}"
        return self._req("GET", f"/users/by-username/{username}", allow_404=True)

    def add_or_extend(self, user_id: int, days: int):
        """Создаёт пользователя, если его нет, иначе продлевает срок.
        Возвращает (uuid, username, expiry_ms, subscription_url) — совместимо
        по форме с прежним xui.add_or_extend."""
        username = f"tg{user_id}"
        now_ms = int(time.time() * 1000)
        add_ms = days * 86400 * 1000
        user = self.get_user(user_id)

        if user:
            base = _to_ms(user.get("expireAt")) or 0
            base = base if base > now_ms else now_ms
            new_ms = base + add_ms
            payload = {
                "id": user["id"],
                "expireAt": _to_iso(new_ms),
                "status": "ACTIVE",
                "activeInternalSquads": [self.squad],
            }
            resp = self._req("PATCH", "/users", json=payload)
        else:
            new_ms = now_ms + add_ms
            payload = {
                "username": username,
                "status": "ACTIVE",
                "expireAt": _to_iso(new_ms),
                "trafficLimitBytes": 0,
                "trafficLimitStrategy": "NO_RESET",
                "activeInternalSquads": [self.squad],
                "telegramId": int(user_id),
            }
            resp = self._req("POST", "/users", json=payload)

        uuid = resp.get("id")
        link = resp.get("subscriptionUrl", "")
        expiry_ms = _to_ms(resp.get("expireAt")) or new_ms
        return uuid, username, expiry_ms, link

    def get_link(self, user_id: int) -> str:
        """Ссылка-подписка пользователя (или '' если пользователя нет)."""
        user = self.get_user(user_id)
        return user.get("subscriptionUrl", "") if user else ""

    def set_enabled(self, user_id: int, enabled: bool):
        user = self.get_user(user_id)
        if not user:
            raise RemnaError("пользователь не найден (нет ключа)")
        self._req("PATCH", "/users", json={
            "id": user["id"],
            "status": "ACTIVE" if enabled else "DISABLED",
        })

    def delete_client(self, user_id: int):
        user = self.get_user(user_id)
        if not user:
            raise RemnaError("пользователь не найден (нет ключа)")
        self._req("DELETE", f"/users/{user['id']}")


# ---------- само-тест: python remna.py ----------
if __name__ == "__main__":
    import sys
    config.validate()
    r = Remna()
    test_uid = 999000111  # заведомо тестовый id
    print("1) создаём/продлеваем пользователя на 1 день...")
    uuid, uname, exp, link = r.add_or_extend(test_uid, 1)
    print(f"   uuid={uuid}\n   username={uname}\n   expiry={_to_iso(exp)}\n   link={link}")
    print("2) читаем ссылку-подписку...")
    print(f"   link={r.get_link(test_uid)}")
    print("3) продлеваем ещё на 7 дней...")
    _, _, exp2, _ = r.add_or_extend(test_uid, 7)
    print(f"   new expiry={_to_iso(exp2)}")
    print("4) выключаем и включаем...")
    r.set_enabled(test_uid, False)
    r.set_enabled(test_uid, True)
    print("   ок")
    if "--keep" not in sys.argv:
        print("5) удаляем тестового пользователя...")
        r.delete_client(test_uid)
        print("   удалён")
    print("\nВСЁ ОК ✅  Клиент Remnawave работает.")
