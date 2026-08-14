"""Конвертация валют через Frankfurter (ЕЦБ, без ключа)."""

from __future__ import annotations

from dataclasses import dataclass

from .http import ServiceError, get_json

_LATEST_URL = "https://api.frankfurter.app/latest"

# Псевдонимы для удобного ввода.
_ALIASES = {
    "РУБ": "RUB",
    "РУБЛЬ": "RUB",
    "РУБЛЕЙ": "RUB",
    "ДОЛЛАР": "USD",
    "ДОЛЛАРОВ": "USD",
    "БАКС": "USD",
    "$": "USD",
    "ЕВРО": "EUR",
    "€": "EUR",
    "ФУНТ": "GBP",
    "£": "GBP",
    "ЙЕНА": "JPY",
    "ЮАНЬ": "CNY",
    "ЛИРА": "TRY",
    "ТЕНГЕ": "KZT",
    "ГРИВНА": "UAH",
}


def normalize_currency(code: str) -> str:
    code = code.strip().upper()
    return _ALIASES.get(code, code)


@dataclass(frozen=True)
class Conversion:
    amount: float
    from_currency: str
    to_currency: str
    result: float
    rate: float
    date: str


async def convert(amount: float, from_currency: str, to_currency: str) -> Conversion:
    frm = normalize_currency(from_currency)
    to = normalize_currency(to_currency)

    if frm == to:
        return Conversion(amount, frm, to, amount, 1.0, "—")

    data = await get_json(
        _LATEST_URL,
        params={"amount": amount, "from": frm, "to": to},
    )
    rates = data.get("rates") or {}
    if to not in rates:
        raise ServiceError(
            f"Не удалось конвертировать {frm} → {to}. "
            "Проверьте коды валют (например, USD, EUR, RUB)."
        )
    result = rates[to]
    rate = result / amount if amount else 0.0
    return Conversion(amount, frm, to, result, rate, data.get("date", "—"))
