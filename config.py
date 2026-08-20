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
    testnet_base_url: str

    # Рынок
    symbol: str
    interval: str
    leverage: int
    margin_type: str

    # Стратегия
    strategy: str  # 'ema_rsi' | 'fast_rsi'

    # Риск
    risk_per_trade: float
    stop_loss_pct: float
    take_profit_pct: float
    take_profit_roi: float   # тейк по доходности на маржу (с учётом плеча); 0 = выкл
    max_position_usdt: float
    max_drawdown_pct: float  # стоп бота при просадке от пика (0 = выкл)

    # Индикаторы (EMA/RSI стратегия)
    ema_fast: int
    ema_slow: int
    rsi_period: int
    rsi_overbought: float
    rsi_oversold: float

    # Fast RSI 2.0
    rsi_limit: float
    body_ema: int

    # ATR-стоп
    use_atr_stop: bool
    atr_period: int
    atr_sl_mult: float
    atr_tp_mult: float

    # Трендовый фильтр старшего ТФ
    trend_filter: bool
    trend_interval: str
    trend_ema: int

    # Трейлинг-стоп
    trailing_stop: bool       # использовать трейлинг вместо фикс. тейка
    trailing_callback: float  # откат трейлинга в % (0.1..5)

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
            testnet_base_url=os.getenv(
                "TESTNET_BASE_URL", "https://demo-fapi.binance.com"
            ).rstrip("/"),
            symbol=os.getenv("SYMBOL", "BTCUSDT").upper(),
            interval=os.getenv("INTERVAL", "15m"),
            leverage=_get_int("LEVERAGE", 3),
            margin_type=os.getenv("MARGIN_TYPE", "ISOLATED").upper(),
            strategy=os.getenv("STRATEGY", "ema_rsi").strip().lower(),
            risk_per_trade=_get_float("RISK_PER_TRADE", 0.01),
            stop_loss_pct=_get_float("STOP_LOSS_PCT", 0.015),
            take_profit_pct=_get_float("TAKE_PROFIT_PCT", 0.03),
            take_profit_roi=_get_float("TAKE_PROFIT_ROI", 0.0),
            max_position_usdt=_get_float("MAX_POSITION_USDT", 100.0),
            max_drawdown_pct=_get_float("MAX_DRAWDOWN_PCT", 0.25),
            ema_fast=_get_int("EMA_FAST", 9),
            ema_slow=_get_int("EMA_SLOW", 21),
            rsi_period=_get_int("RSI_PERIOD", 14),
            rsi_overbought=_get_float("RSI_OVERBOUGHT", 70.0),
            rsi_oversold=_get_float("RSI_OVERSOLD", 30.0),
            rsi_limit=_get_float("RSI_LIMIT", 40.0),
            body_ema=_get_int("BODY_EMA", 30),
            use_atr_stop=_get_bool("USE_ATR_STOP", False),
            atr_period=_get_int("ATR_PERIOD", 14),
            atr_sl_mult=_get_float("ATR_SL_MULT", 2.0),
            atr_tp_mult=_get_float("ATR_TP_MULT", 4.0),
            trend_filter=_get_bool("TREND_FILTER", False),
            trend_interval=os.getenv("TREND_INTERVAL", "4h"),
            trend_ema=_get_int("TREND_EMA", 200),
            trailing_stop=_get_bool("TRAILING_STOP", False),
            trailing_callback=_get_float("TRAILING_CALLBACK", 1.0),
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
        if self.strategy not in ("ema_rsi", "fast_rsi"):
            raise ValueError("STRATEGY должен быть ema_rsi или fast_rsi.")
        if self.ema_fast >= self.ema_slow:
            raise ValueError("EMA_FAST должен быть меньше EMA_SLOW.")
        if self.margin_type not in ("ISOLATED", "CROSSED"):
            raise ValueError("MARGIN_TYPE должен быть ISOLATED или CROSSED.")
        if not (0 < self.risk_per_trade <= 1):
            raise ValueError("RISK_PER_TRADE должен быть в диапазоне (0, 1].")
        if not (0 <= self.max_drawdown_pct < 1):
            raise ValueError("MAX_DRAWDOWN_PCT должен быть в диапазоне [0, 1).")
        if self.take_profit_roi < 0:
            raise ValueError("TAKE_PROFIT_ROI не может быть отрицательным.")
        if self.trailing_stop and not (0.1 <= self.trailing_callback <= 5):
            raise ValueError("TRAILING_CALLBACK должен быть в диапазоне [0.1, 5].")
        if self.leverage < 1:
            raise ValueError("LEVERAGE должен быть >= 1.")
