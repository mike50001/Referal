"""Индикаторная стратегия: пересечение EMA с фильтром по RSI."""
from __future__ import annotations

from dataclasses import dataclass
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
    ema_fast: float
    ema_slow: float
    rsi: float


class EmaRsiStrategy:
    """
    Логика:
      - Бычье пересечение (EMA_fast снизу вверх пересекает EMA_slow) и RSI не
        в зоне перекупленности -> сигнал LONG.
      - Медвежье пересечение (EMA_fast сверху вниз) и RSI не в зоне
        перепроданности -> сигнал SHORT.
      - Обратное пересечение против открытой позиции -> CLOSE.

    Решение принимается по ЗАКРЫТОЙ свече (последняя строка — уже закрытая),
    чтобы избежать перерисовки сигнала внутри формирующейся свечи.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def min_bars(self) -> int:
        return max(self.cfg.ema_slow, self.cfg.rsi_period) + 5

    def evaluate(self, df: pd.DataFrame, position_side: str | None) -> Decision:
        """
        df: DataFrame со столбцом 'close' (индекс — время закрытия свечи),
            где последняя строка — последняя ЗАКРЫТАЯ свеча.
        position_side: 'LONG', 'SHORT' или None — текущая открытая позиция.
        """
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

        base = Decision(
            signal=Signal.NONE,
            reason="нет сигнала",
            price=price,
            ema_fast=f_now,
            ema_slow=s_now,
            rsi=r_now,
        )

        # Сначала — выход из позиции при обратном пересечении.
        if position_side == "LONG" and cross_down:
            base.signal = Signal.CLOSE
            base.reason = "медвежье пересечение EMA — закрываем LONG"
            return base
        if position_side == "SHORT" and cross_up:
            base.signal = Signal.CLOSE
            base.reason = "бычье пересечение EMA — закрываем SHORT"
            return base

        # Вход разрешён только когда позиции нет.
        if position_side is None:
            if cross_up and r_now < self.cfg.rsi_overbought:
                base.signal = Signal.LONG
                base.reason = (
                    f"бычье пересечение EMA (RSI={r_now:.1f} < "
                    f"{self.cfg.rsi_overbought:.0f})"
                )
            elif cross_down and r_now > self.cfg.rsi_oversold:
                base.signal = Signal.SHORT
                base.reason = (
                    f"медвежье пересечение EMA (RSI={r_now:.1f} > "
                    f"{self.cfg.rsi_oversold:.0f})"
                )

        return base
