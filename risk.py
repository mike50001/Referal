"""Риск-менеджмент: расчёт размера позиции и уровней SL/TP."""
from __future__ import annotations

from dataclasses import dataclass

from config import Config


@dataclass
class OrderPlan:
    quantity: float          # объём в базовом активе (например, BTC)
    notional_usdt: float     # номинал позиции в USDT
    stop_loss: float         # цена стоп-лосса
    take_profit: float       # цена тейк-профита
    sl_distance_pct: float   # фактическая дистанция до стопа (доля от цены)


class RiskManager:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def _sl_tp(self, side: str, price: float, atr: float | None) -> tuple[float, float, float]:
        """Возвращает (stop_loss, take_profit, sl_distance_pct)."""
        if self.cfg.use_atr_stop and atr and atr > 0:
            sl_dist = self.cfg.atr_sl_mult * atr
            tp_dist = self.cfg.atr_tp_mult * atr
        else:
            sl_dist = self.cfg.stop_loss_pct * price
            tp_dist = self.cfg.take_profit_pct * price

        if side == "LONG":
            stop_loss = price - sl_dist
            take_profit = price + tp_dist
        else:  # SHORT
            stop_loss = price + sl_dist
            take_profit = price - tp_dist

        sl_distance_pct = sl_dist / price if price > 0 else 0.0
        return stop_loss, take_profit, sl_distance_pct

    def build_plan(
        self,
        side: str,
        price: float,
        balance_usdt: float,
        atr: float | None = None,
    ) -> OrderPlan:
        """
        Рассчитывает объём так, чтобы потеря на стоп-лоссе была примерно равна
        RISK_PER_TRADE от баланса, но не превышала MAX_POSITION_USDT по номиналу.

        side: 'LONG' или 'SHORT'. atr: значение ATR (для ATR-стопа).
        """
        stop_loss, take_profit, sl_dist_pct = self._sl_tp(side, price, atr)

        risk_amount = balance_usdt * self.cfg.risk_per_trade
        # Номинал, при котором движение на sl_dist_pct даёт убыток risk_amount.
        notional = risk_amount / sl_dist_pct if sl_dist_pct > 0 else 0.0
        notional = min(notional, self.cfg.max_position_usdt)

        quantity = notional / price if price > 0 else 0.0

        return OrderPlan(
            quantity=quantity,
            notional_usdt=notional,
            stop_loss=stop_loss,
            take_profit=take_profit,
            sl_distance_pct=sl_dist_pct,
        )
