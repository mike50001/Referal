"""Справка по стране через REST Countries (без ключа)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .http import ServiceError, get_json

_COUNTRY_URL = "https://restcountries.com/v3.1/name/{name}"
_FIELDS = (
    "name,capital,region,subregion,population,area,languages,currencies,"
    "flag,timezones,idd,car,tld,maps"
)


@dataclass(frozen=True)
class Country:
    name: str
    official_name: str
    flag: str
    capital: str
    region: str
    subregion: str
    population: int
    area: float
    languages: list[str] = field(default_factory=list)
    currencies: list[str] = field(default_factory=list)
    timezones: list[str] = field(default_factory=list)
    phone_code: str = ""
    drives_on: str = ""
    maps_url: str = ""


async def get_country(name: str, *, language: str = "ru") -> Country:
    name = name.strip()
    if not name:
        raise ServiceError("Укажите название страны.")

    data = await get_json(
        _COUNTRY_URL.format(name=name),
        params={"fields": _FIELDS},
    )
    if not isinstance(data, list) or not data:
        raise ServiceError(f"Не нашёл страну «{name}».")

    c = data[0]

    native = c.get("name", {})
    languages = list((c.get("languages") or {}).values())

    currencies = []
    for code, info in (c.get("currencies") or {}).items():
        symbol = info.get("symbol", "")
        cur_name = info.get("name", "")
        label = f"{cur_name} ({code}{' ' + symbol if symbol else ''})"
        currencies.append(label)

    idd = c.get("idd", {})
    root = idd.get("root", "")
    suffixes = idd.get("suffixes") or [""]
    phone_code = f"{root}{suffixes[0]}" if root else ""

    return Country(
        name=native.get("common", name),
        official_name=native.get("official", ""),
        flag=c.get("flag", "🏳️"),
        capital=", ".join(c.get("capital") or []) or "—",
        region=c.get("region", "—"),
        subregion=c.get("subregion", ""),
        population=c.get("population", 0),
        area=c.get("area", 0.0),
        languages=languages,
        currencies=currencies,
        timezones=c.get("timezones") or [],
        phone_code=phone_code,
        drives_on=(c.get("car") or {}).get("side", ""),
        maps_url=(c.get("maps") or {}).get("googleMaps", ""),
    )
