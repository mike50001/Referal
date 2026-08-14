"""Общий асинхронный HTTP-клиент с таймаутами и повторными запросами."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_HEADERS = {"User-Agent": "traveler-telegram-bot/1.0 (+https://t.me)"}

# Единый клиент переиспользуется между запросами (пул соединений).
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=_DEFAULT_TIMEOUT,
            headers=_HEADERS,
            follow_redirects=True,
        )
    return _client


async def close_client() -> None:
    """Закрыть общий клиент (вызывается при остановке бота)."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


class ServiceError(Exception):
    """Ошибка обращения к внешнему сервису, понятная пользователю."""


async def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    retries: int = 2,
) -> Any:
    """Выполнить GET-запрос и вернуть JSON.

    Повторяет запрос при сетевых сбоях с экспоненциальной задержкой.
    Бросает ServiceError при неудаче.
    """
    client = _get_client()
    last_exc: Exception | None = None

    for attempt in range(retries + 1):
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            # Ответ 4xx повторять бессмысленно.
            if 400 <= exc.response.status_code < 500:
                logger.warning("HTTP %s от %s", exc.response.status_code, url)
                raise ServiceError(
                    f"Сервис вернул ошибку {exc.response.status_code}."
                ) from exc
            last_exc = exc
        except (httpx.HTTPError, ValueError) as exc:
            last_exc = exc

        if attempt < retries:
            await asyncio.sleep(2 ** attempt * 0.5)

    logger.error("Не удалось получить %s: %s", url, last_exc)
    raise ServiceError("Сервис временно недоступен, попробуйте позже.") from last_exc
