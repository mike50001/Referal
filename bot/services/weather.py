"""Прогноз погоды через Open-Meteo (без ключа)."""

from __future__ import annotations

from dataclasses import dataclass

from .geocoding import Place, find_place
from .http import get_json

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Коды погоды WMO -> описание и эмодзи.
_WEATHER_CODES: dict[int, tuple[str, str]] = {
    0: ("Ясно", "☀️"),
    1: ("Преимущественно ясно", "🌤"),
    2: ("Переменная облачность", "⛅️"),
    3: ("Пасмурно", "☁️"),
    45: ("Туман", "🌫"),
    48: ("Изморозь", "🌫"),
    51: ("Слабая морось", "🌦"),
    53: ("Морось", "🌦"),
    55: ("Сильная морось", "🌧"),
    56: ("Ледяная морось", "🌧"),
    57: ("Сильная ледяная морось", "🌧"),
    61: ("Небольшой дождь", "🌦"),
    63: ("Дождь", "🌧"),
    65: ("Сильный дождь", "🌧"),
    66: ("Ледяной дождь", "🌧"),
    67: ("Сильный ледяной дождь", "🌧"),
    71: ("Небольшой снег", "🌨"),
    73: ("Снег", "🌨"),
    75: ("Сильный снегопад", "❄️"),
    77: ("Снежная крупа", "🌨"),
    80: ("Небольшие ливни", "🌦"),
    81: ("Ливни", "🌧"),
    82: ("Сильные ливни", "⛈"),
    85: ("Снежные ливни", "🌨"),
    86: ("Сильные снежные ливни", "❄️"),
    95: ("Гроза", "⛈"),
    96: ("Гроза с градом", "⛈"),
    99: ("Сильная гроза с градом", "⛈"),
}


def describe_code(code: int) -> tuple[str, str]:
    return _WEATHER_CODES.get(code, ("Неизвестно", "🌍"))


@dataclass(frozen=True)
class Weather:
    place: Place
    temperature: float
    feels_like: float
    humidity: int
    wind_speed: float
    code: int
    is_day: bool
    temp_max: float
    temp_min: float

    @property
    def description(self) -> str:
        return describe_code(self.code)[0]

    @property
    def emoji(self) -> str:
        return describe_code(self.code)[1]


async def get_weather(city: str, *, language: str = "ru") -> Weather:
    place = await find_place(city, language=language)
    data = await get_json(
        _FORECAST_URL,
        params={
            "latitude": place.latitude,
            "longitude": place.longitude,
            "current": (
                "temperature_2m,apparent_temperature,relative_humidity_2m,"
                "weather_code,wind_speed_10m,is_day"
            ),
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": "auto",
            "forecast_days": 1,
        },
    )
    current = data.get("current", {})
    daily = data.get("daily", {})

    def _first(seq, default=0.0):
        return seq[0] if isinstance(seq, list) and seq else default

    return Weather(
        place=place,
        temperature=current.get("temperature_2m", 0.0),
        feels_like=current.get("apparent_temperature", 0.0),
        humidity=current.get("relative_humidity_2m", 0),
        wind_speed=current.get("wind_speed_10m", 0.0),
        code=current.get("weather_code", -1),
        is_day=bool(current.get("is_day", 1)),
        temp_max=_first(daily.get("temperature_2m_max")),
        temp_min=_first(daily.get("temperature_2m_min")),
    )
