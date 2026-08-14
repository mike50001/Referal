"""Оффлайн-тесты чистой логики сервисов (без сетевых запросов)."""

import asyncio

from bot.services.checklist import get_checklist, list_categories
from bot.services.currency import convert, normalize_currency
from bot.services.phrasebook import available_languages, phrases_for
from bot.services.weather import describe_code


def test_normalize_currency_aliases():
    assert normalize_currency("руб") == "RUB"
    assert normalize_currency("$") == "USD"
    assert normalize_currency("€") == "EUR"
    assert normalize_currency("usd") == "USD"
    # Неизвестный код возвращается как есть (в верхнем регистре).
    assert normalize_currency("sek") == "SEK"


def test_same_currency_conversion_is_offline():
    # Конвертация одинаковых валют не должна ходить в сеть.
    result = asyncio.run(convert(50, "EUR", "EUR"))
    assert result.result == 50
    assert result.rate == 1.0


def test_weather_codes():
    assert describe_code(0)[0] == "Ясно"
    assert describe_code(95)[0] == "Гроза"
    # Неизвестный код не должен падать.
    assert describe_code(-1)[0] == "Неизвестно"


def test_phrasebook_complete():
    langs = [code for code, _ in available_languages()]
    assert "en" in langs and "es" in langs
    for code in langs:
        data = phrases_for(code)
        assert data is not None
        assert "lang" in data
        # Кроме служебного ключа lang должны быть фразы.
        assert len(data) > 1


def test_checklists_have_items():
    cats = [key for key, _ in list_categories()]
    assert "documents" in cats
    for key in cats:
        title, items = get_checklist(key)
        assert title
        assert len(items) > 0
