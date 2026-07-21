"""Курсы обмена и расчёт суммы сделки.

Курсы задаёт обменник вручную — командой /setrate прямо в боте
(интернет не нужен). Курсы направленные: для каждой пары свой курс
«туда» и «обратно» (спред обменника). Значения сохраняются в файл,
поэтому переживают перезапуск бота.
"""
from __future__ import annotations

import json
import logging
import pathlib

logger = logging.getLogger("exchange-bot.rates")

# Файл, где хранятся заданные обменником курсы (рядом с проектом).
_RATES_FILE = pathlib.Path(__file__).resolve().parent.parent / "rates_data.json"

# Текущие курсы обменника. Значения по умолчанию можно менять командой /setrate.
#   kzt_give_kzt — сколько ТЕНГЕ за 1 РУБЛЬ, когда клиент отдаёт ТЕНГЕ (→ рубли)
#   kzt_give_rub — сколько ТЕНГЕ за 1 РУБЛЬ, когда клиент отдаёт РУБЛИ (→ тенге)
#   thb_give_thb — сколько РУБЛЕЙ за 1 БАТ, когда клиент отдаёт БАТЫ (→ рубли)
#   thb_give_rub — сколько РУБЛЕЙ за 1 БАТ, когда клиент отдаёт РУБЛИ (→ баты)
QUOTE_KEYS = ("kzt_give_kzt", "kzt_give_rub", "thb_give_thb", "thb_give_rub")
_quotes: dict[str, float] = {
    "kzt_give_kzt": 6.0,
    "kzt_give_rub": 5.6,
    "thb_give_thb": 2.33,
    "thb_give_rub": 2.55,
}

# Как показывать курсы клиенту/админу: (заголовок, ключ курса, единица).
# Показываем ровно те числа, что задаёт обменник.
_RATE_DISPLAY = [
    ("🇰🇿 Тенге → 🇷🇺 Рубль", "kzt_give_kzt", "тенге за 1 рубль"),
    ("🇷🇺 Рубль → 🇰🇿 Тенге", "kzt_give_rub", "тенге за 1 рубль"),
    ("🇷🇺 Рубль → 🇹🇭 Бат", "thb_give_rub", "рублей за 1 бат"),
    ("🇹🇭 Бат → 🇷🇺 Рубль", "thb_give_thb", "рублей за 1 бат"),
]

# Курс в формате обменника для конкретного направления сделки.
_QUOTE_FOR_PAIR = {
    ("KZT", "RUB"): ("kzt_give_kzt", "тенге за 1 рубль"),
    ("RUB", "KZT"): ("kzt_give_rub", "тенге за 1 рубль"),
    ("THB", "RUB"): ("thb_give_thb", "рублей за 1 бат"),
    ("RUB", "THB"): ("thb_give_rub", "рублей за 1 бат"),
}


def _fmt_quote(value: float) -> str:
    """Формат курса: сохраняет десятичную часть (6 → «6.0», 5.6 → «5.6»)."""
    text = f"{value:.4f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return text


def quote_text(give: str, get: str) -> str | None:
    """Курс направления в записи обменника, напр. «6.0 тенге за 1 рубль»."""
    item = _QUOTE_FOR_PAIR.get((give, get))
    if item is None:
        return None
    key, unit = item
    return f"{_fmt_quote(_quotes[key])} {unit}"


# --- Хранилище курсов -----------------------------------------------------


def load() -> None:
    """Загружает сохранённые курсы из файла (вызывается при старте бота)."""
    try:
        if _RATES_FILE.exists():
            data = json.loads(_RATES_FILE.read_text("utf-8"))
            for key in QUOTE_KEYS:
                if key in data:
                    _quotes[key] = float(data[key])
            logger.info("Курсы загружены из файла: %s", _quotes)
    except Exception as exc:
        logger.warning("Не удалось загрузить курсы из файла: %s", exc)


def _save() -> None:
    try:
        _RATES_FILE.write_text(json.dumps(_quotes, ensure_ascii=False), "utf-8")
    except Exception as exc:
        logger.warning("Не удалось сохранить курсы в файл: %s", exc)


def get_quotes() -> dict[str, float]:
    return dict(_quotes)


def set_quotes(kzt_give_kzt: float, kzt_give_rub: float,
               thb_give_thb: float, thb_give_rub: float) -> None:
    _quotes.update(
        kzt_give_kzt=kzt_give_kzt,
        kzt_give_rub=kzt_give_rub,
        thb_give_thb=thb_give_thb,
        thb_give_rub=thb_give_rub,
    )
    _save()


def _pair_rate(give: str, get: str) -> float | None:
    """Курс: сколько единиц `get` за 1 единицу `give`. None, если пара не задана."""
    q = _quotes
    if (give, get) == ("KZT", "RUB"):
        return 1 / q["kzt_give_kzt"]
    if (give, get) == ("RUB", "KZT"):
        return q["kzt_give_rub"]
    if (give, get) == ("THB", "RUB"):
        return q["thb_give_thb"]
    if (give, get) == ("RUB", "THB"):
        return 1 / q["thb_give_rub"]
    return None


# --- Форматирование и расчёт ----------------------------------------------


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
    amount: float | None,
    side: str,
    markup_percent: float = 0.0,
) -> dict[str, float] | None:
    """Считает недостающую сторону сделки по курсу обменника.

    side == "give": клиент отдаёт `amount` в `give` → сколько получит в `get`.
    side == "get":  клиент хочет получить `amount` в `get` → сколько отдаст в `give`.

    Возвращает {"counter": сумма, "rate": курс_get_за_1_give} или None,
    если для пары нет заданного курса (тогда сумму назовёт менеджер).
    """
    if amount is None:
        return None

    rate = _pair_rate(give, get)
    if rate is None:
        logger.info("Нет курса для пары %s/%s", give, get)
        return None

    margin = markup_percent / 100.0
    if side == "get":
        counter = (amount / rate) * (1 + margin)      # платит больше
        effective_rate = rate / (1 + margin)
    else:
        counter = amount * rate * (1 - margin)         # получает меньше
        effective_rate = rate * (1 - margin)

    return {"counter": counter, "rate": effective_rate}


def _rates_lines() -> list[str]:
    return [
        f"• {title}: <b>{_fmt_quote(_quotes[key])}</b> ({unit})"
        for title, key, unit in _RATE_DISPLAY
    ]


async def client_rates_text() -> str:
    """Текст курсов для клиента (кнопка «Узнать курс»)."""
    lines = ["📈 <b>Актуальный курс:</b>\n", *_rates_lines()]
    lines.append("\n<i>Точную сумму подтвердит менеджер при оформлении заявки.</i>")
    return "\n".join(lines)


async def snapshot_text() -> str:
    """Текст текущих курсов для админа."""
    return "\n".join(["📈 <b>Курсы обменника сейчас:</b>\n", *_rates_lines()])
