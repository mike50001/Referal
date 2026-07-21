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


class RiskManager:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def build_plan(self, side: str, price: float, balance_usdt: float) -> OrderPlan:
        """
        Рассчитывает объём так, чтобы потеря на стоп-лоссе была примерно равна
        RISK_PER_TRADE от баланса, но не превышала MAX_POSITION_USDT по номиналу.

        side: 'LONG' или 'SHORT'.
        """
        risk_amount = balance_usdt * self.cfg.risk_per_trade
        sl_distance_pct = self.cfg.stop_loss_pct

        # Номинал, при котором движение на sl_distance_pct даёт убыток risk_amount.
        notional = risk_amount / sl_distance_pct if sl_distance_pct > 0 else 0.0
        notional = min(notional, self.cfg.max_position_usdt)

        quantity = notional / price if price > 0 else 0.0

        if side == "LONG":
            stop_loss = price * (1 - self.cfg.stop_loss_pct)
            take_profit = price * (1 + self.cfg.take_profit_pct)
        else:  # SHORT
            stop_loss = price * (1 + self.cfg.stop_loss_pct)
            take_profit = price * (1 - self.cfg.take_profit_pct)

        return OrderPlan(
            quantity=quantity,
            notional_usdt=notional,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
