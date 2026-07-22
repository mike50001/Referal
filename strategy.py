"""Торговые стратегии бота.

Все стратегии реализуют общий интерфейс:
  - min_bars() -> int          : сколько свечей нужно для расчёта
  - evaluate(df, position_side): -> Decision по последней ЗАКРЫТОЙ свече

Доступные стратегии выбираются через build_strategy(cfg):
  - 'ema_rsi'  : пересечение EMA с фильтром RSI
  - 'fast_rsi' : Fast RSI 2.0 (RSI + EMA размера тела свечи)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pandas as pd

from config import Config
from indicators import ema, rsi


class Signal(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    CLOSE = "CLOSE"
    NONE = "NONE"


@dataclass
class Decision:
    signal: Signal
    reason: str
    price: float
    indicators: dict = field(default_factory=dict)  # для логов/отладки


class Strategy:
    """Базовый класс стратегии."""

    name = "base"

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def min_bars(self) -> int:  # pragma: no cover - переопределяется
        raise NotImplementedError

    def evaluate(self, df: pd.DataFrame, position_side: str | None) -> Decision:  # pragma: no cover
        raise NotImplementedError


class EmaRsiStrategy(Strategy):
    """
    Пересечение EMA (fast/slow) с фильтром по RSI.
      - Бычье пересечение + RSI не перекуплен  -> LONG
      - Медвежье пересечение + RSI не перепродан -> SHORT
      - Обратное пересечение против позиции      -> CLOSE
    Решение по закрытой свече (последняя строка df уже закрыта).
    """

    name = "ema_rsi"

    def min_bars(self) -> int:
        return max(self.cfg.ema_slow, self.cfg.rsi_period) + 5

    def evaluate(self, df: pd.DataFrame, position_side: str | None) -> Decision:
        close = df["close"]
        ema_f = ema(close, self.cfg.ema_fast)
        ema_s = ema(close, self.cfg.ema_slow)
        rsi_v = rsi(close, self.cfg.rsi_period)

        price = float(close.iloc[-1])
        f_now, f_prev = float(ema_f.iloc[-1]), float(ema_f.iloc[-2])
        s_now, s_prev = float(ema_s.iloc[-1]), float(ema_s.iloc[-2])
        r_now = float(rsi_v.iloc[-1])

        cross_up = f_prev <= s_prev and f_now > s_now
        cross_down = f_prev >= s_prev and f_now < s_now

        info = {"ema_fast": f_now, "ema_slow": s_now, "rsi": r_now}
        d = Decision(Signal.NONE, "нет сигнала", price, info)

        if position_side == "LONG" and cross_down:
            return Decision(Signal.CLOSE, "медвежье пересечение EMA — закрываем LONG", price, info)
        if position_side == "SHORT" and cross_up:
            return Decision(Signal.CLOSE, "бычье пересечение EMA — закрываем SHORT", price, info)

        if position_side is None:
            if cross_up and r_now < self.cfg.rsi_overbought:
                d = Decision(Signal.LONG,
                             f"бычье пересечение EMA (RSI={r_now:.1f}<{self.cfg.rsi_overbought:.0f})",
                             price, info)
            elif cross_down and r_now > self.cfg.rsi_oversold:
                d = Decision(Signal.SHORT,
                             f"медвежье пересечение EMA (RSI={r_now:.1f}>{self.cfg.rsi_oversold:.0f})",
                             price, info)
        return d


class FastRsiStrategy(Strategy):
    """
    Fast RSI 2.0 (из учебного курса, урок 13).

    Индикаторы: RSI + EMA размера тела свечи.
      - body = |close - open|
      - avg_body = EMA(BODY_EMA) от body
      - свечи с телом < avg_body/2 считаются слишком мелкими (шум)

    Правила (RSI_LIMIT — параметр, напр. 40):
      - RSI < RSI_LIMIT        и body > avg_body/4 -> открыть LONG
      - RSI > RSI_LIMIT        и body > avg_body/2 -> закрыть LONG
      - RSI > (100 - RSI_LIMIT) и body > avg_body/4 -> открыть SHORT
      - RSI < (100 - RSI_LIMIT) и body > avg_body/2 -> закрыть SHORT

    Решение по закрытой свече.
    """

    name = "fast_rsi"

    def min_bars(self) -> int:
        return max(self.cfg.body_ema, self.cfg.rsi_period) + 5

    def evaluate(self, df: pd.DataFrame, position_side: str | None) -> Decision:
        close = df["close"]
        body = (df["close"] - df["open"]).abs()
        avg_body = ema(body, self.cfg.body_ema)
        rsi_v = rsi(close, self.cfg.rsi_period)

        price = float(close.iloc[-1])
        b_now = float(body.iloc[-1])
        ab = float(avg_body.iloc[-1])
        r_now = float(rsi_v.iloc[-1])
        limit = self.cfg.rsi_limit
        hi_limit = 100 - limit

        info = {"rsi": r_now, "body": b_now, "avg_body": ab}
        d = Decision(Signal.NONE, "нет сигнала", price, info)

        # Слишком мелкая свеча — игнорируем (защита от шума).
        if ab <= 0 or b_now < ab / 2:
            d.reason = "свеча слишком мелкая — пропуск"
            return d

        big_quarter = b_now > ab / 4
        big_half = b_now > ab / 2

        # Выход из позиции.
        if position_side == "LONG" and r_now > limit and big_half:
            return Decision(Signal.CLOSE, f"RSI={r_now:.1f}>{limit:.0f} — закрываем LONG", price, info)
        if position_side == "SHORT" and r_now < hi_limit and big_half:
            return Decision(Signal.CLOSE, f"RSI={r_now:.1f}<{hi_limit:.0f} — закрываем SHORT", price, info)

        # Вход.
        if position_side is None:
            if r_now < limit and big_quarter:
                d = Decision(Signal.LONG, f"RSI={r_now:.1f}<{limit:.0f} (перепроданность)", price, info)
            elif r_now > hi_limit and big_quarter:
                d = Decision(Signal.SHORT, f"RSI={r_now:.1f}>{hi_limit:.0f} (перекупленность)", price, info)
        return d


_STRATEGIES = {
    EmaRsiStrategy.name: EmaRsiStrategy,
    FastRsiStrategy.name: FastRsiStrategy,
}


def build_strategy(cfg: Config) -> Strategy:
    cls = _STRATEGIES.get(cfg.strategy)
    if cls is None:
        raise ValueError(f"Неизвестная стратегия: {cfg.strategy}. "
                         f"Доступны: {', '.join(_STRATEGIES)}")
    return cls(cfg)
