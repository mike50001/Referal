"""Местное время в городе по его часовому поясу."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .geocoding import Place, find_place
from .http import ServiceError


@dataclass(frozen=True)
class LocalTime:
    place: Place
    now: datetime
    utc_offset: str


def _format_offset(dt: datetime) -> str:
    offset = dt.utcoffset()
    if offset is None:
        return "UTC"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    return f"UTC{sign}{total_minutes // 60:02d}:{total_minutes % 60:02d}"


async def get_local_time(city: str, *, language: str = "ru") -> LocalTime:
    place = await find_place(city, language=language)
    try:
        tz = ZoneInfo(place.timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ServiceError(
            f"Не удалось определить часовой пояс для {place.display}."
        ) from exc

    now = datetime.now(tz)
    return LocalTime(place=place, now=now, utc_offset=_format_offset(now))
