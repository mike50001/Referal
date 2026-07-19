"""Получение курсов валют и расчёт суммы обмена.

Источник — бесплатный API https://open.er-api.com (база USD, без ключа).
Курсы кэшируются, чтобы не дёргать API на каждое сообщение.
USDT считается равным доллару (стейблкоин ≈ $1).
"""
from __future__ import annotations

import logging
import time

import aiohttp

logger = logging.getLogger("exchange-bot.rates")

API_URL = "https://open.er-api.com/v6/latest/USD"
_CACHE_TTL = 600  # секунд (10 минут)
_cache: dict[str, object] = {"ts": 0.0, "rates": {}}


async def _get_rates() -> dict[str, float]:
    """Возвращает словарь «валюта → сколько единиц за 1 USD». С кэшированием."""
    now = time.time()
    cached = _cache.get("rates") or {}
    if cached and now - float(_cache["ts"]) < _CACHE_TTL:
        return cached  # type: ignore[return-value]

    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(API_URL) as resp:
            resp.raise_for_status()
            data = await resp.json()

    if data.get("result") != "success" or "rates" not in data:
        raise RuntimeError("Некорректный ответ API курсов")

    rates: dict[str, float] = dict(data["rates"])
    rates.setdefault("USD", 1.0)
    rates["USDT"] = rates["USD"]  # стейблкоин привязан к доллару

    _cache["rates"] = rates
    _cache["ts"] = now
    return rates


def fmt(value: float) -> str:
    """Аккуратно форматирует сумму: разделяет тысячи, убирает лишние нули."""
    av = abs(value)
    if av >= 1:
        decimals = 2
    elif av >= 0.01:
        decimals = 4
    else:
        decimals = 6
    text = f"{value:,.{decimals}f}".replace(",", " ")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


async def calculate(
    give: str,
    get: str,
    amount: float,
    side: str,
    markup_percent: float,
) -> dict[str, float] | None:
    """Считает недостающую сторону сделки по текущему курсу с наценкой.

    side == "give": клиент отдаёт `amount` в валюте `give` → сколько получит в `get`.
    side == "get":  клиент хочет получить `amount` в валюте `get` → сколько отдаст в `give`.

    Наценка всегда в пользу обменника (клиент получает меньше / платит больше).
    Возвращает {"counter": сумма_другой_стороны, "rate": курс_get_за_1_give}
    или None, если курс недоступен (тогда сумму назовёт менеджер).
    """
    try:
        rates = await _get_rates()
    except Exception as exc:  # сеть/недоступность API — не роняем заявку
        logger.warning("Не удалось получить курсы валют: %s", exc)
        return None

    if give not in rates or get not in rates:
        logger.warning("Нет курса для пары %s/%s", give, get)
        return None

    margin = markup_percent / 100.0
    market_rate = rates[get] / rates[give]  # сколько GET за 1 GIVE (рыночный)

    if side == "get":
        # Клиент фиксирует сумму к получению → считаем, сколько отдать (дороже).
        counter = amount * (rates[give] / rates[get]) * (1 + margin)
        effective_rate = market_rate / (1 + margin)
    else:
        # Клиент фиксирует сумму к отдаче → считаем, сколько получит (меньше).
        counter = amount * market_rate * (1 - margin)
        effective_rate = market_rate * (1 - margin)

    return {"counter": counter, "rate": effective_rate}


# Валюты, которые бот показывает в диагностике /rates.
SNAPSHOT_CODES = ["RUB", "KZT", "THB", "USDT"]


# Подписи валют для клиентского вида курсов.
_CURRENCY_LABELS = {
    "RUB": "🇷🇺 рубль",
    "KZT": "🇰🇿 тенге",
    "THB": "🇹🇭 бат",
    "USDT": "💵 USDT",
}

# Пары, которые показываем клиенту в «Узнать курс» (в обе стороны).
CLIENT_PAIRS = [
    ("KZT", "RUB"),
    ("RUB", "KZT"),
    ("RUB", "THB"),
    ("THB", "RUB"),
]


def _label(code: str) -> str:
    return _CURRENCY_LABELS.get(code, code)


async def client_rates_text() -> str:
    """Дружелюбный текст курсов для клиента (кнопка «Узнать курс»)."""
    try:
        rates = await _get_rates()
    except Exception as exc:
        logger.warning("Курсы недоступны для клиента: %s", exc)
        return (
            "📈 Курс временно недоступен.\n\n"
            "Оставьте заявку — менеджер свяжется с вами и назовёт актуальный курс."
        )

    lines = ["📈 <b>Актуальный курс</b> (ориентировочно):\n"]
    for give, get in CLIENT_PAIRS:
        if give in rates and get in rates:
            rate = rates[get] / rates[give]
            lines.append(f"• 1 {_label(give)} ≈ {fmt(rate)} {_label(get)}")
    lines.append("\n<i>Точную сумму подтвердит менеджер при оформлении заявки.</i>")
    return "\n".join(lines)


async def snapshot_text() -> str:
    """Текст для команды /rates: текущие курсы или причина ошибки."""
    try:
        rates = await _get_rates()
    except Exception as exc:
        return f"⚠️ Не удалось получить курсы: {exc}"

    base = "USDT"
    lines = [f"📈 <b>Текущие курсы</b> (кэш 10 мин), 1 {base} ="]
    for code in SNAPSHOT_CODES:
        if code == base or code not in rates:
            continue
        lines.append(f"• {fmt(rates[code] / rates[base])} {code}")
    return "\n".join(lines)
