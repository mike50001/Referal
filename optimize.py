"""Оптимизатор параметров стратегии ema_rsi (перебор + walk-forward).

Идея честной проверки:
  - история делится по времени на TRAIN (первая часть) и TEST (последняя);
  - каждая комбинация параметров прогоняется отдельно на TRAIN и на TEST;
  - выводятся комбинации, которые прибыльны И на train, И на out-of-sample
    (test). Настройки, хорошие только на train, — это переобучение, им не верим.

Быстрый векторный бэктест (индикаторы считаются один раз на срез).

Запуск:
    python optimize.py --csv ml/data/BTCUSDT_1h.csv
    python optimize.py --csv ml/data/BTCUSDT_1h.csv --fee 0.0004 --split 0.6
"""
from __future__ import annotations

import argparse
import itertools

import numpy as np
import pandas as pd


def _ema(a: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(a).ewm(span=n, adjust=False).mean().to_numpy()


def _rsi(a: np.ndarray, n: int = 14) -> np.ndarray:
    s = pd.Series(a)
    d = s.diff()
    up = d.clip(lower=0.0)
    dn = -d.clip(upper=0.0)
    au = up.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    ad = dn.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    rs = au / ad
    out = 100 - 100 / (1 + rs)
    return out.where(ad != 0, 100.0).to_numpy()


def simulate(df: pd.DataFrame, ema_fast: int, ema_slow: int, tp: float, sl: float,
             rsi_ob: float = 70, rsi_os: float = 30, rsi_period: int = 14,
             fee: float = 0.0004) -> dict:
    """Быстрый бэктест ema_rsi на одном срезе. PnL — сумма доходностей сделок (в %)."""
    o = df["open"].to_numpy(float)
    c = df["close"].to_numpy(float)
    hi = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    ef = _ema(c, ema_fast)
    es = _ema(c, ema_slow)
    rsi = _rsi(c, rsi_period)

    warm = max(ema_slow, rsi_period) + 2
    n = len(c)
    fee2 = 2 * fee
    pos = None          # ('LONG'/'SHORT', entry_price)
    pnl_sum = 0.0
    trades = wins = 0

    for i in range(warm, n):
        # выход по SL/TP внутри свечи
        if pos is not None:
            side, entry = pos
            ret = None
            if side == "LONG":
                if lo[i] <= entry * (1 - sl):
                    ret = -sl
                elif hi[i] >= entry * (1 + tp):
                    ret = tp
            else:
                if hi[i] >= entry * (1 + sl):
                    ret = -sl
                elif lo[i] <= entry * (1 - tp):
                    ret = tp
            if ret is not None:
                pnl_sum += ret - fee2
                trades += 1
                wins += 1 if ret > 0 else 0
                pos = None

        cross_up = ef[i - 1] <= es[i - 1] and ef[i] > es[i]
        cross_down = ef[i - 1] >= es[i - 1] and ef[i] < es[i]

        # выход по обратному пересечению
        if pos is not None:
            side, entry = pos
            if (side == "LONG" and cross_down) or (side == "SHORT" and cross_up):
                ret = (c[i] - entry) / entry if side == "LONG" else (entry - c[i]) / entry
                pnl_sum += ret - fee2
                trades += 1
                wins += 1 if ret > 0 else 0
                pos = None

        # вход
        if pos is None:
            if cross_up and rsi[i] < rsi_ob:
                pos = ("LONG", c[i])
            elif cross_down and rsi[i] > rsi_os:
                pos = ("SHORT", c[i])

    winrate = (wins / trades * 100) if trades else 0.0
    return {"trades": trades, "winrate": winrate, "pnl_pct": pnl_sum * 100}


def main() -> None:
    p = argparse.ArgumentParser(description="Оптимизатор параметров ema_rsi")
    p.add_argument("--csv", required=True)
    p.add_argument("--fee", type=float, default=0.0004)
    p.add_argument("--split", type=float, default=0.6, help="доля данных на train")
    p.add_argument("--min-trades", type=int, default=8, help="мин. сделок на test")
    args = p.parse_args()

    df = pd.read_csv(args.csv, index_col=0, parse_dates=True)
    k = int(len(df) * args.split)
    train, test = df.iloc[:k], df.iloc[k:]
    print(f"Данные: {len(df)} свечей | train={len(train)} test={len(test)}")
    print(f"Период: {df.index[0]} .. {df.index[-1]}")
    print("=" * 78)

    # сетка перебора
    ema_fasts = [5, 9, 12]
    ema_slows = [21, 26, 50, 100]
    tps = [0.02, 0.03, 0.05]
    sls = [0.01, 0.015, 0.02]

    combos = [(ef, es, tp, sl)
              for ef, es, tp, sl in itertools.product(ema_fasts, ema_slows, tps, sls)
              if ef < es]
    print(f"Проверяю {len(combos)} комбинаций (train + out-of-sample test)...\n")

    results = []
    for ef, es, tp, sl in combos:
        tr = simulate(train, ef, es, tp, sl, fee=args.fee)
        te = simulate(test, ef, es, tp, sl, fee=args.fee)
        results.append({
            "ema_fast": ef, "ema_slow": es, "tp": tp, "sl": sl,
            "train_pnl": tr["pnl_pct"], "test_pnl": te["pnl_pct"],
            "test_trades": te["trades"], "test_wr": te["winrate"],
        })

    # робастные: прибыльны и на train, и на test, и достаточно сделок
    robust = [r for r in results
              if r["train_pnl"] > 0 and r["test_pnl"] > 0
              and r["test_trades"] >= args.min_trades]
    robust.sort(key=lambda r: r["test_pnl"], reverse=True)

    hdr = f"{'EMA':>7} {'TP%':>5} {'SL%':>5} {'train%':>8} {'test%':>8} {'сделок':>7} {'wr%':>6}"
    print("ТОП устойчивых конфигов (прибыль на train И на out-of-sample):")
    print(hdr)
    print("-" * 78)
    if robust:
        for r in robust[:15]:
            print(f"{r['ema_fast']:>3}/{r['ema_slow']:<3} {r['tp']*100:>5.1f} "
                  f"{r['sl']*100:>5.1f} {r['train_pnl']:>+8.2f} {r['test_pnl']:>+8.2f} "
                  f"{r['test_trades']:>7} {r['test_wr']:>6.1f}")
    else:
        print("  Устойчивых конфигов НЕ найдено — ни одна комбинация не показала")
        print("  плюс одновременно на train и на out-of-sample. Честный сигнал:")
        print("  на этих данных надёжного edge у ema_rsi нет.")
    print("=" * 78)

    # для сравнения — текущий дефолт
    cur = simulate(test, 9, 21, 0.03, 0.015, fee=args.fee)
    print(f"Текущий конфиг (EMA 9/21, TP3% SL1.5%) на test: "
          f"P&L={cur['pnl_pct']:+.2f}% сделок={cur['trades']} wr={cur['winrate']:.1f}%")

    print("\n⚠️  Даже лучший конфиг на истории не гарантирует прибыль в реале.")
    print("   Бери устойчивый (плюс на train И test), а не самый жирный на train.")
    print("   После выбора — обязательно проверка на testnet.")


if __name__ == "__main__":
    main()
