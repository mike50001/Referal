"""Отчёт по торговле бота за период (данные берутся прямо с биржи).

Считает по реальным сделкам аккаунта: реализованный P&L, комиссии, число
сделок, винрейт, а также текущую открытую позицию и баланс.

Запуск (на сервере, где есть .env с ключами):
    python report.py --days 2
    python report.py --days 7 --symbol BTCUSDT
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

from config import Config
from exchange import BinanceFutures


def _fmt_ts(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%m-%d %H:%M")


def main() -> None:
    p = argparse.ArgumentParser(description="Отчёт по торговле бота")
    p.add_argument("--days", type=float, default=2.0)
    p.add_argument("--symbol", default=None)
    args = p.parse_args()

    cfg = Config.load()
    if args.symbol:
        cfg.symbol = args.symbol.upper()

    ex = BinanceFutures(cfg)         # настраивает клиента и (для testnet) demo-URL
    client = ex.client
    start_ms = int((time.time() - args.days * 86400) * 1000)

    net_env = "TESTNET" if cfg.use_testnet else "MAINNET"
    print("=" * 60)
    print(f"ОТЧЁТ ПО ТОРГОВЛЕ | {net_env} | {cfg.symbol} | за {args.days:g} дн.")
    print("=" * 60)

    # --- сделки за период ---
    trades = client.futures_account_trades(symbol=cfg.symbol, startTime=start_ms)

    closes = [t for t in trades if float(t["realizedPnl"]) != 0.0]
    gross = sum(float(t["realizedPnl"]) for t in trades)
    comm = sum(float(t["commission"]) for t in trades)
    net = gross - comm
    wins = [t for t in closes if float(t["realizedPnl"]) > 0]
    losses = [t for t in closes if float(t["realizedPnl"]) < 0]
    n_close = len(closes)
    winrate = (len(wins) / n_close * 100) if n_close else 0.0

    print(f"Всего исполнений (fills):   {len(trades)}")
    print(f"Закрывающих сделок:         {n_close}")
    print(f"  прибыльных:               {len(wins)}")
    print(f"  убыточных:                {len(losses)}")
    print(f"  винрейт:                  {winrate:.1f}%")
    print("-" * 60)
    print(f"Реализованный P&L (gross):  {gross:+.4f} USDT")
    print(f"Комиссии:                   -{comm:.4f} USDT")
    print(f"ЧИСТЫЙ P&L (net):           {net:+.4f} USDT")
    print("=" * 60)

    # --- список закрывающих сделок ---
    if closes:
        print("Закрывающие сделки (время UTC):")
        for t in closes[-20:]:
            pnl = float(t["realizedPnl"])
            side = "SELL" if t["side"] == "SELL" else "BUY"
            mark = "✅" if pnl > 0 else "❌"
            print(f"  {_fmt_ts(int(t['time']))}  {side:4}  "
                  f"price={float(t['price']):.2f}  PnL={pnl:+.4f} {mark}")
        print("=" * 60)
    else:
        print("За период закрытых сделок не было "
              "(для ema_rsi на 15m это нормально).")
        print("=" * 60)

    # --- текущая позиция ---
    pos = ex.get_position()
    if pos:
        info = client.futures_position_information(symbol=cfg.symbol)[0]
        upnl = float(info.get("unRealizedProfit", 0.0))
        print(f"Открыта позиция: {pos['side']} qty={pos['amt']} "
              f"вход={pos['entry']:.2f}  нереализ. P&L={upnl:+.4f} USDT")
    else:
        print("Открытых позиций сейчас нет.")

    # --- баланс ---
    bal = ex.get_balance_usdt()
    print(f"Доступный баланс: {bal:.2f} USDT")
    print("=" * 60)


if __name__ == "__main__":
    main()
