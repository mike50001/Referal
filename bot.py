"""Главный цикл торгового бота для фьючерсов Binance.

Возможности:
  - выбор стратегии через .env (STRATEGY=ema_rsi | fast_rsi);
  - фиксированный или ATR-стоп (USE_ATR_STOP);
  - трендовый фильтр старшего ТФ (TREND_FILTER);
  - защита от просадки: стоп бота при просадке > MAX_DRAWDOWN_PCT;
  - режимы testnet и DRY_RUN.

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
from indicators import atr as atr_indicator
from risk import RiskManager
from strategy import Decision, Strategy, Signal, build_strategy


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
        self.strategy: Strategy = build_strategy(cfg)
        self.risk = RiskManager(cfg)
        self._running = True
        self._peak_balance: float | None = None  # для контроля просадки

    def start(self) -> None:
        mode = "TESTNET" if self.cfg.use_testnet else "MAINNET (РЕАЛЬНЫЕ ДЕНЬГИ)"
        dry = " [DRY_RUN — ордера НЕ отправляются]" if self.cfg.dry_run else ""
        self.log.info("=" * 64)
        self.log.info("Запуск бота | %s%s", mode, dry)
        self.log.info("Стратегия=%s Символ=%s ТФ=%s плечо=x%d",
                      self.strategy.name, self.cfg.symbol, self.cfg.interval, self.cfg.leverage)
        self.log.info("ATR-стоп=%s Тренд-фильтр=%s(%s/EMA%d) Max-DD=%.0f%%",
                      self.cfg.use_atr_stop, self.cfg.trend_filter,
                      self.cfg.trend_interval, self.cfg.trend_ema,
                      self.cfg.max_drawdown_pct * 100)
        self.log.info("=" * 64)

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

            slept = 0
            while self._running and slept < self.cfg.poll_interval_sec:
                time.sleep(1)
                slept += 1

        self.log.info("Бот остановлен.")

    # ---------- защита от просадки ----------

    def _drawdown_ok(self, balance: float) -> bool:
        """False -> просадка превысила лимит, новые входы запрещены."""
        if self.cfg.max_drawdown_pct <= 0:
            return True
        if self._peak_balance is None or balance > self._peak_balance:
            self._peak_balance = balance
        dd = (self._peak_balance - balance) / self._peak_balance if self._peak_balance else 0.0
        if dd >= self.cfg.max_drawdown_pct:
            self.log.warning(
                "Просадка %.1f%% >= лимита %.1f%% (пик=%.2f, сейчас=%.2f) — "
                "новые сделки заблокированы.",
                dd * 100, self.cfg.max_drawdown_pct * 100, self._peak_balance, balance,
            )
            return False
        return True

    # ---------- основной тик ----------

    def _tick(self) -> None:
        need = max(200, self.strategy.min_bars(), self.cfg.atr_period + 5)
        df = self.ex.get_klines(limit=need)
        if len(df) < self.strategy.min_bars():
            self.log.warning("Недостаточно свечей (%d), жду...", len(df))
            return

        position = self.ex.get_position()
        pos_side = position["side"] if position else None

        decision = self.strategy.evaluate(df, pos_side)
        ind = " ".join(f"{k}={v:.2f}" for k, v in decision.indicators.items())
        self.log.info("price=%.2f %s pos=%s -> %s (%s)",
                      decision.price, ind, pos_side or "нет",
                      decision.signal.value, decision.reason)

        if decision.signal == Signal.NONE:
            return
        if decision.signal == Signal.CLOSE:
            self._handle_close(position)
        elif decision.signal in (Signal.LONG, Signal.SHORT):
            self._handle_open(decision, df)

    def _handle_close(self, position: dict | None) -> None:
        if position is None:
            return
        if self.cfg.dry_run:
            self.log.info("[DRY_RUN] закрыл бы позицию %s", position["side"])
            return
        self.ex.close_position(position)
        self.ex.cancel_open_orders()

    def _handle_open(self, decision: Decision, df) -> None:
        side = decision.signal.value  # 'LONG' / 'SHORT'

        # Трендовый фильтр старшего ТФ: не входим против тренда.
        if self.cfg.trend_filter:
            try:
                trend = self.ex.get_trend()
            except BinanceAPIException as e:
                self.log.warning("Не удалось получить тренд: %s", e.message)
                trend = "FLAT"
            if trend in ("LONG", "SHORT") and trend != side:
                self.log.info("Пропуск %s: тренд старшего ТФ = %s", side, trend)
                return

        balance = self.ex.get_balance_usdt() if not self.cfg.dry_run else 1000.0

        # Защита от просадки.
        if not self._drawdown_ok(balance):
            return

        # ATR для стопа (если включён).
        atr_val = None
        if self.cfg.use_atr_stop:
            atr_series = atr_indicator(df, self.cfg.atr_period)
            atr_val = float(atr_series.iloc[-1])

        plan = self.risk.build_plan(side, decision.price, balance, atr=atr_val)
        qty = self.ex.round_qty(plan.quantity)

        self.log.info(
            "Сигнал %s: qty=%s notional=%.2f SL=%.2f TP=%.2f (SL-dist=%.2f%%, баланс=%.2f)",
            side, qty, plan.notional_usdt, plan.stop_loss, plan.take_profit,
            plan.sl_distance_pct * 100, balance,
        )

        if qty <= 0 or not self.ex.qty_ok(qty, decision.price):
            self.log.warning(
                "Объём %s не проходит фильтры биржи (minQty/minNotional). "
                "Увеличьте MAX_POSITION_USDT или баланс.", qty,
            )
            return

        if self.cfg.dry_run:
            mode = "трейлинг" if self.cfg.trailing_stop else "SL/TP"
            self.log.info("[DRY_RUN] открыл бы %s qty=%s + %s", side, qty, mode)
            return

        self.ex.open_market(side, qty)
        if self.cfg.trailing_stop:
            # Жёсткий стоп-лосс (защита) + трейлинг вместо фикс. тейка.
            self.ex.place_stop_loss(side, plan.stop_loss)
            self.ex.place_trailing_stop(side, qty, self.cfg.trailing_callback)
        else:
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
