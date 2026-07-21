"""Обёртка над Binance USDT-M Futures API (python-binance)."""
from __future__ import annotations

import logging
import math
from typing import Optional

import pandas as pd
from binance.client import Client
from binance.enums import (
    FUTURE_ORDER_TYPE_MARKET,
    FUTURE_ORDER_TYPE_STOP_MARKET,
    FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
    SIDE_BUY,
    SIDE_SELL,
    TIME_IN_FORCE_GTC,
)
from binance.exceptions import BinanceAPIException

from config import Config

log = logging.getLogger("bot.exchange")


class BinanceFutures:
    """Тонкая обёртка с округлением по фильтрам и удобными методами."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = Client(
            cfg.api_key,
            cfg.api_secret,
            testnet=cfg.use_testnet,
        )
        # python-binance сам подставляет testnet URL при testnet=True,
        # но зафиксируем явно для futures.
        if cfg.use_testnet:
            self.client.FUTURES_URL = "https://testnet.binancefuture.com/fapi"

        self._step_size: float = 0.0
        self._tick_size: float = 0.0
        self._min_qty: float = 0.0
        self._min_notional: float = 0.0
        self._load_symbol_filters()

    # ---------- инициализация / метаданные ----------

    def _load_symbol_filters(self) -> None:
        info = self.client.futures_exchange_info()
        sym = next(
            (s for s in info["symbols"] if s["symbol"] == self.cfg.symbol), None
        )
        if sym is None:
            raise ValueError(f"Символ {self.cfg.symbol} не найден на бирже.")
        for f in sym["filters"]:
            if f["filterType"] == "LOT_SIZE":
                self._step_size = float(f["stepSize"])
                self._min_qty = float(f["minQty"])
            elif f["filterType"] == "PRICE_FILTER":
                self._tick_size = float(f["tickSize"])
            elif f["filterType"] in ("MIN_NOTIONAL", "NOTIONAL"):
                self._min_notional = float(f.get("notional", f.get("minNotional", 0)))
        log.info(
            "Фильтры %s: step=%s tick=%s minQty=%s minNotional=%s",
            self.cfg.symbol, self._step_size, self._tick_size,
            self._min_qty, self._min_notional,
        )

    def setup_account(self) -> None:
        """Устанавливает плечо и тип маржи (идемпотентно)."""
        try:
            self.client.futures_change_leverage(
                symbol=self.cfg.symbol, leverage=self.cfg.leverage
            )
            log.info("Плечо установлено: x%s", self.cfg.leverage)
        except BinanceAPIException as e:
            log.warning("Не удалось сменить плечо: %s", e.message)
        try:
            self.client.futures_change_margin_type(
                symbol=self.cfg.symbol, marginType=self.cfg.margin_type
            )
            log.info("Тип маржи: %s", self.cfg.margin_type)
        except BinanceAPIException as e:
            # -4046 = No need to change margin type.
            if e.code != -4046:
                log.warning("Не удалось сменить тип маржи: %s", e.message)

    # ---------- округление под фильтры биржи ----------

    def _round_step(self, value: float, step: float) -> float:
        if step <= 0:
            return value
        return math.floor(value / step) * step

    def round_qty(self, qty: float) -> float:
        return round(self._round_step(qty, self._step_size), 8)

    def round_price(self, price: float) -> float:
        return round(self._round_step(price, self._tick_size), 8)

    def qty_ok(self, qty: float, price: float) -> bool:
        if qty < self._min_qty:
            return False
        if self._min_notional and qty * price < self._min_notional:
            return False
        return True

    # ---------- рыночные данные ----------

    def get_klines(self, limit: int = 200) -> pd.DataFrame:
        raw = self.client.futures_klines(
            symbol=self.cfg.symbol, interval=self.cfg.interval, limit=limit
        )
        df = pd.DataFrame(
            raw,
            columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades",
                "taker_base", "taker_quote", "ignore",
            ],
        )
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = df[col].astype(float)
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
        df = df.set_index("close_time")
        # Отбрасываем последнюю (ещё формирующуюся) свечу.
        return df.iloc[:-1]

    def get_price(self) -> float:
        t = self.client.futures_symbol_ticker(symbol=self.cfg.symbol)
        return float(t["price"])

    # ---------- баланс и позиция ----------

    def get_balance_usdt(self) -> float:
        for b in self.client.futures_account_balance():
            if b["asset"] == "USDT":
                return float(b["availableBalance"])
        return 0.0

    def get_position(self) -> Optional[dict]:
        """Возвращает {'side': 'LONG'|'SHORT', 'amt': float, 'entry': float}
        или None, если позиции нет."""
        positions = self.client.futures_position_information(symbol=self.cfg.symbol)
        for p in positions:
            amt = float(p["positionAmt"])
            if amt != 0:
                return {
                    "side": "LONG" if amt > 0 else "SHORT",
                    "amt": abs(amt),
                    "entry": float(p["entryPrice"]),
                }
        return None

    # ---------- ордера ----------

    def open_market(self, side: str, qty: float) -> dict:
        order_side = SIDE_BUY if side == "LONG" else SIDE_SELL
        order = self.client.futures_create_order(
            symbol=self.cfg.symbol,
            side=order_side,
            type=FUTURE_ORDER_TYPE_MARKET,
            quantity=qty,
        )
        log.info("Открыт %s market qty=%s (orderId=%s)",
                 side, qty, order.get("orderId"))
        return order

    def place_sl_tp(self, side: str, stop_loss: float, take_profit: float) -> None:
        """Ставит защитные reduce-only ордера STOP_MARKET и TAKE_PROFIT_MARKET."""
        close_side = SIDE_SELL if side == "LONG" else SIDE_BUY
        sl = self.round_price(stop_loss)
        tp = self.round_price(take_profit)
        try:
            self.client.futures_create_order(
                symbol=self.cfg.symbol,
                side=close_side,
                type=FUTURE_ORDER_TYPE_STOP_MARKET,
                stopPrice=sl,
                closePosition=True,
                timeInForce=TIME_IN_FORCE_GTC,
            )
            self.client.futures_create_order(
                symbol=self.cfg.symbol,
                side=close_side,
                type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
                stopPrice=tp,
                closePosition=True,
                timeInForce=TIME_IN_FORCE_GTC,
            )
            log.info("SL=%s TP=%s выставлены", sl, tp)
        except BinanceAPIException as e:
            log.error("Ошибка при выставлении SL/TP: %s", e.message)

    def close_position(self, position: dict) -> None:
        close_side = SIDE_SELL if position["side"] == "LONG" else SIDE_BUY
        self.client.futures_create_order(
            symbol=self.cfg.symbol,
            side=close_side,
            type=FUTURE_ORDER_TYPE_MARKET,
            quantity=self.round_qty(position["amt"]),
            reduceOnly=True,
        )
        log.info("Позиция %s закрыта (qty=%s)", position["side"], position["amt"])

    def cancel_open_orders(self) -> None:
        try:
            self.client.futures_cancel_all_open_orders(symbol=self.cfg.symbol)
        except BinanceAPIException as e:
            log.warning("Не удалось отменить ордера: %s", e.message)
