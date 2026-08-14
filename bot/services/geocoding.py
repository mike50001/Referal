"""Геокодирование названий городов через Open-Meteo (без ключа)."""

from __future__ import annotations

from dataclasses import dataclass

from .http import ServiceError, get_json

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"


@dataclass(frozen=True)
class Place:
    name: str
    country: str
    country_code: str
    latitude: float
    longitude: float
    timezone: str
    admin1: str | None = None

    @property
    def display(self) -> str:
        parts = [self.name]
        if self.admin1 and self.admin1 != self.name:
            parts.append(self.admin1)
        parts.append(self.country)
        return ", ".join(parts)


async def find_place(query: str, *, language: str = "ru") -> Place:
    """Найти город по названию. Возвращает наиболее релевантный результат."""
    query = query.strip()
    if not query:
        raise ServiceError("Укажите название города.")

    data = await get_json(
        _GEOCODE_URL,
        params={"name": query, "count": 1, "language": language, "format": "json"},
    )
    results = data.get("results") or []
    if not results:
        raise ServiceError(f"Не нашёл место «{query}». Проверьте название.")

    r = results[0]
    return Place(
        name=r.get("name", query),
        country=r.get("country", ""),
        country_code=r.get("country_code", ""),
        latitude=r["latitude"],
        longitude=r["longitude"],
        timezone=r.get("timezone", "UTC"),
        admin1=r.get("admin1"),
    )
