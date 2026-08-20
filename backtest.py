"""Простой бэктест стратегий на исторических свечах Binance.

Скачивает публичные свечи (ключи API не нужны) и прогоняет ту же стратегию,
что и живой бот. Учитывает SL/TP (в т.ч. ATR) и комиссию.

Запуск:
    python backtest.py --symbol BTCUSDT --interval 1h --limit 1000
    python backtest.py --strategy fast_rsi --interval 15m
"""
from __future__ import annotations

import argparse

import pandas as pd
from binance.client import Client

from config import Config
from indicators import atr as atr_indicator
from risk import RiskManager
from strategy import Signal, build_strategy


def fetch_klines(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    client = Client()  # публичные данные, ключи не требуются
    raw = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(
        raw,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades",
            "taker_base", "taker_quote", "ignore",
        ],
    )
    for col in ("open", "high", "low", "close"):
        df[col] = df[col].astype(float)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
    return df.set_index("close_time")


def compute_stats(cfg: Config, df: pd.DataFrame, fee: float = 0.0004) -> dict:
    """Прогоняет стратегию по df и возвращает метрики (без печати).
    Возвращает: trades, wins, winrate, pnl (USDT от старта 1000), pnl_pct."""
    strat = build_strategy(cfg)
    risk = RiskManager(cfg)
    min_bars = strat.min_bars()

    atr_series = atr_indicator(df, cfg.atr_period) if cfg.use_atr_stop else None

    balance = 1000.0
    start_balance = balance
    position = None  # dict: side, entry, qty, sl, tp
    trades = 0
    wins = 0

    for i in range(min_bars, len(df)):
        window = df.iloc[: i + 1]
        candle = df.iloc[i]
        pos_side = position["side"] if position else None

        # Проверяем срабатывание SL/TP по диапазону свечи.
        if position is not None:
            hi, lo = candle["high"], candle["low"]
            exit_price = None
            if position["side"] == "LONG":
                if lo <= position["sl"]:
                    exit_price = position["sl"]
                elif hi >= position["tp"]:
                    exit_price = position["tp"]
            else:  # SHORT
                if hi >= position["sl"]:
                    exit_price = position["sl"]
                elif lo <= position["tp"]:
                    exit_price = position["tp"]
            if exit_price is not None:
                pnl = _pnl(position, exit_price, fee)
                balance += pnl
                trades += 1
                wins += 1 if pnl > 0 else 0
                position = None
                pos_side = None

        decision = strat.evaluate(window, pos_side)

        if decision.signal == Signal.CLOSE and position is not None:
            pnl = _pnl(position, decision.price, fee)
            balance += pnl
            trades += 1
            wins += 1 if pnl > 0 else 0
            position = None
        elif decision.signal in (Signal.LONG, Signal.SHORT) and position is None:
            atr_val = float(atr_series.iloc[i]) if atr_series is not None else None
            plan = risk.build_plan(decision.signal.value, decision.price, balance, atr=atr_val)
            if plan.quantity > 0:
                position = {
                    "side": decision.signal.value,
                    "entry": decision.price,
                    "qty": plan.quantity,
                    "sl": plan.stop_loss,
                    "tp": plan.take_profit,
                }

    pnl_total = balance - start_balance
    winrate = (wins / trades * 100) if trades else 0.0
    return {
        "trades": trades, "wins": wins, "winrate": winrate,
        "pnl": pnl_total, "pnl_pct": pnl_total / start_balance * 100,
        "balance": balance,
    }


def run_backtest(cfg: Config, df: pd.DataFrame, fee: float = 0.0004) -> None:
    s = compute_stats(cfg, df, fee)
    print("=" * 50)
    print(f"Стратегия:     {cfg.strategy}")
    print(f"Символ:        {cfg.symbol} {cfg.interval}")
    print(f"ATR-стоп:      {cfg.use_atr_stop}")
    print(f"Свечей:        {len(df)}")
    print(f"Сделок:        {s['trades']}")
    print(f"Прибыльных:    {s['wins']} ({s['winrate']:.1f}%)")
    print(f"Итог баланс:   {s['balance']:.2f} USDT")
    print(f"P&L:           {s['pnl']:+.2f} USDT ({s['pnl_pct']:+.2f}%)")
    print("=" * 50)


def _pnl(position: dict, exit_price: float, fee: float) -> float:
    entry, qty = position["entry"], position["qty"]
    if position["side"] == "LONG":
        gross = (exit_price - entry) * qty
    else:
        gross = (entry - exit_price) * qty
    fees = (entry + exit_price) * qty * fee
    return gross - fees


def main() -> None:
    p = argparse.ArgumentParser(description="Бэктест торговых стратегий")
    p.add_argument("--symbol", default=None)
    p.add_argument("--interval", default=None)
    p.add_argument("--strategy", default=None, choices=["ema_rsi", "fast_rsi"])
    p.add_argument("--limit", type=int, default=1000)
    args = p.parse_args()

    # Конфиг индикаторов берём из .env, но API-ключи для бэктеста не нужны.
    import os
    os.environ.setdefault("BINANCE_API_KEY", "backtest")
    os.environ.setdefault("BINANCE_API_SECRET", "backtest")
    cfg = Config.load()
    if args.symbol:
        cfg.symbol = args.symbol.upper()
    if args.interval:
        cfg.interval = args.interval
    if args.strategy:
        cfg.strategy = args.strategy

    df = fetch_klines(cfg.symbol, cfg.interval, args.limit)
    run_backtest(cfg, df)


if __name__ == "__main__":
    main()
