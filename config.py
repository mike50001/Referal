"""Загрузка и валидация конфигурации из переменных окружения (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _get_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    return float(raw) if raw not in (None, "") else default


def _get_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    return int(raw) if raw not in (None, "") else default


def _get_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw in (None, ""):
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on")


@dataclass
class Config:
    # API
    api_key: str
    api_secret: str
    use_testnet: bool

    # Рынок
    symbol: str
    interval: str
    leverage: int
    margin_type: str

    # Риск
    risk_per_trade: float
    stop_loss_pct: float
    take_profit_pct: float
    max_position_usdt: float

    # Индикаторы
    ema_fast: int
    ema_slow: int
    rsi_period: int
    rsi_overbought: float
    rsi_oversold: float

    # Прочее
    poll_interval_sec: int
    dry_run: bool
    log_level: str

    @classmethod
    def load(cls) -> "Config":
        cfg = cls(
            api_key=os.getenv("BINANCE_API_KEY", ""),
            api_secret=os.getenv("BINANCE_API_SECRET", ""),
            use_testnet=_get_bool("USE_TESTNET", True),
            symbol=os.getenv("SYMBOL", "BTCUSDT").upper(),
            interval=os.getenv("INTERVAL", "15m"),
            leverage=_get_int("LEVERAGE", 3),
            margin_type=os.getenv("MARGIN_TYPE", "ISOLATED").upper(),
            risk_per_trade=_get_float("RISK_PER_TRADE", 0.01),
            stop_loss_pct=_get_float("STOP_LOSS_PCT", 0.015),
            take_profit_pct=_get_float("TAKE_PROFIT_PCT", 0.03),
            max_position_usdt=_get_float("MAX_POSITION_USDT", 100.0),
            ema_fast=_get_int("EMA_FAST", 9),
            ema_slow=_get_int("EMA_SLOW", 21),
            rsi_period=_get_int("RSI_PERIOD", 14),
            rsi_overbought=_get_float("RSI_OVERBOUGHT", 70.0),
            rsi_oversold=_get_float("RSI_OVERSOLD", 30.0),
            poll_interval_sec=_get_int("POLL_INTERVAL_SEC", 30),
            dry_run=_get_bool("DRY_RUN", False),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if not self.api_key or not self.api_secret:
            raise ValueError(
                "Не заданы BINANCE_API_KEY / BINANCE_API_SECRET. "
                "Скопируйте .env.example в .env и заполните ключи."
            )
        if self.ema_fast >= self.ema_slow:
            raise ValueError("EMA_FAST должен быть меньше EMA_SLOW.")
        if self.margin_type not in ("ISOLATED", "CROSSED"):
            raise ValueError("MARGIN_TYPE должен быть ISOLATED или CROSSED.")
        if not (0 < self.risk_per_trade <= 1):
            raise ValueError("RISK_PER_TRADE должен быть в диапазоне (0, 1].")
        if self.leverage < 1:
            raise ValueError("LEVERAGE должен быть >= 1.")
