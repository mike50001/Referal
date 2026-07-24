"""Скачивание длинной истории фьючерсных свечей Binance в CSV (ключи не нужны).

Пример:
    python -m ml.fetch_data --symbol BTCUSDT --interval 1h --days 720
    python ml/fetch_data.py --symbol ETHUSDT --interval 15m --days 365
"""
from __future__ import annotations

import argparse
import os
import time

import pandas as pd
from binance.client import Client

_COLS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades",
    "taker_base", "taker_quote", "ignore",
]


def fetch(symbol: str, interval: str, days: int) -> pd.DataFrame:
    client = Client()  # публичные данные
    end = int(time.time() * 1000)
    start = end - days * 24 * 60 * 60 * 1000

    rows: list = []
    cursor = start
    while cursor < end:
        batch = client.futures_klines(
            symbol=symbol, interval=interval, startTime=cursor, limit=1500
        )
        if not batch:
            break
        rows.extend(batch)
        last_open = batch[-1][0]
        nxt = last_open + 1
        if nxt <= cursor:  # защита от зацикливания
            break
        cursor = nxt
        if len(batch) < 1500:
            break
        time.sleep(0.2)  # не долбим API

    df = pd.DataFrame(rows, columns=_COLS)
    df = df.drop_duplicates(subset="open_time")
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
    df = df.set_index("close_time")[["open", "high", "low", "close", "volume"]]
    return df


def main() -> None:
    p = argparse.ArgumentParser(description="Скачать историю Binance в CSV")
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--interval", default="1h")
    p.add_argument("--days", type=int, default=720)
    p.add_argument("--out", default=None)
    args = p.parse_args()

    df = fetch(args.symbol.upper(), args.interval, args.days)
    os.makedirs("ml/data", exist_ok=True)
    out = args.out or f"ml/data/{args.symbol.upper()}_{args.interval}.csv"
    df.to_csv(out)
    print(f"Сохранено {len(df)} свечей -> {out}")
    print(f"Период: {df.index[0]}  ..  {df.index[-1]}")


if __name__ == "__main__":
    main()
