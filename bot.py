"""Главный цикл торгового бота для фьючерсов Binance.

Стратегия: пересечение EMA (fast/slow) с фильтром по RSI.
Работает по закрытым свечам. Поддерживает testnet и DRY_RUN.

Запуск:
    python bot.py
"""
from __future__ import annotations

import logging
import signal
import sys
import time

from binance.exceptions import BinanceAPIException

from config import Config
from exchange import BinanceFutures
from risk import RiskManager
from strategy import Decision, EmaRsiStrategy, Signal


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


class TradingBot:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.log = logging.getLogger("bot")
        self.ex = BinanceFutures(cfg)
        self.strategy = EmaRsiStrategy(cfg)
        self.risk = RiskManager(cfg)
        self._running = True

    def start(self) -> None:
        mode = "TESTNET" if self.cfg.use_testnet else "MAINNET (РЕАЛЬНЫЕ ДЕНЬГИ)"
        dry = " [DRY_RUN — ордера НЕ отправляются]" if self.cfg.dry_run else ""
        self.log.info("=" * 60)
        self.log.info("Запуск бота | %s%s", mode, dry)
        self.log.info(
            "Символ=%s ТФ=%s EMA=%d/%d RSI=%d плечо=x%d",
            self.cfg.symbol, self.cfg.interval,
            self.cfg.ema_fast, self.cfg.ema_slow,
            self.cfg.rsi_period, self.cfg.leverage,
        )
        self.log.info("=" * 60)

        if not self.cfg.dry_run:
            self.ex.setup_account()

        self._install_signal_handlers()
        self._loop()

    def _install_signal_handlers(self) -> None:
        def handler(signum, _frame):
            self.log.info("Получен сигнал %s — останавливаюсь...", signum)
            self._running = False

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def _loop(self) -> None:
        while self._running:
            try:
                self._tick()
            except BinanceAPIException as e:
                self.log.error("Binance API: %s (code=%s)", e.message, e.code)
            except Exception as e:  # noqa: BLE001 — цикл не должен падать
                self.log.exception("Непредвиденная ошибка: %s", e)

            # Спим маленькими шагами, чтобы быстро реагировать на остановку.
            slept = 0
            while self._running and slept < self.cfg.poll_interval_sec:
                time.sleep(1)
                slept += 1

        self.log.info("Бот остановлен.")

    def _tick(self) -> None:
        df = self.ex.get_klines(limit=max(200, self.strategy.min_bars()))
        if len(df) < self.strategy.min_bars():
            self.log.warning("Недостаточно свечей (%d), жду...", len(df))
            return

        position = self.ex.get_position()
        pos_side = position["side"] if position else None

        decision = self.strategy.evaluate(df, pos_side)
        self.log.info(
            "price=%.2f EMA%d=%.2f EMA%d=%.2f RSI=%.1f pos=%s -> %s (%s)",
            decision.price, self.cfg.ema_fast, decision.ema_fast,
            self.cfg.ema_slow, decision.ema_slow, decision.rsi,
            pos_side or "нет", decision.signal.value, decision.reason,
        )

        if decision.signal == Signal.NONE:
            return
        if decision.signal == Signal.CLOSE:
            self._handle_close(position)
        elif decision.signal in (Signal.LONG, Signal.SHORT):
            self._handle_open(decision)

    def _handle_close(self, position: dict | None) -> None:
        if position is None:
            return
        if self.cfg.dry_run:
            self.log.info("[DRY_RUN] закрыл бы позицию %s", position["side"])
            return
        self.ex.close_position(position)
        self.ex.cancel_open_orders()

    def _handle_open(self, decision: Decision) -> None:
        side = decision.signal.value  # 'LONG' / 'SHORT'
        balance = self.ex.get_balance_usdt() if not self.cfg.dry_run else 1000.0
        plan = self.risk.build_plan(side, decision.price, balance)
        qty = self.ex.round_qty(plan.quantity)

        self.log.info(
            "Сигнал %s: qty=%s notional=%.2f USDT SL=%.2f TP=%.2f (баланс=%.2f)",
            side, qty, plan.notional_usdt, plan.stop_loss, plan.take_profit, balance,
        )

        if qty <= 0 or not self.ex.qty_ok(qty, decision.price):
            self.log.warning(
                "Объём %s не проходит фильтры биржи (minQty/minNotional). "
                "Увеличьте MAX_POSITION_USDT или баланс.", qty,
            )
            return

        if self.cfg.dry_run:
            self.log.info("[DRY_RUN] открыл бы %s qty=%s + SL/TP", side, qty)
            return

        self.ex.open_market(side, qty)
        self.ex.place_sl_tp(side, plan.stop_loss, plan.take_profit)


def main() -> int:
    try:
        cfg = Config.load()
    except ValueError as e:
        print(f"Ошибка конфигурации: {e}", file=sys.stderr)
        return 1

    setup_logging(cfg.log_level)
    bot = TradingBot(cfg)
    bot.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
