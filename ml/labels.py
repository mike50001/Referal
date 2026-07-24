"""Разметка (labels) методом тройного барьера (triple-barrier).

Идея (по мотивам López de Prado): для каждого бара t мы «мысленно» открываем
LONG по цене закрытия и смотрим вперёд на horizon баров:
  - верхний барьер  = entry * (1 + tp_mult * atr_pct)   -> тейк-профит
  - нижний барьер   = entry * (1 - sl_mult * atr_pct)   -> стоп-лосс
Что цена тронет первым по пути (по high/low будущих баров), то и определяет метку:
  1 -> сначала достигнут тейк (сделка была бы прибыльной)
  0 -> сначала достигнут стоп, либо истёк горизонт (не прибыльной)

Барьеры масштабируются по ATR (волатильности) — это честнее фиксированных %.

Look-ahead: метка для бара t использует будущие бары t+1..t+horizon. Поэтому
при обучении ОБЯЗАТЕЛЬНО делать разрыв (purge/embargo) между train и test не
меньше horizon — этим занимается train.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _atr_pct(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    return atr / c


def triple_barrier_labels(
    df: pd.DataFrame,
    horizon: int = 12,
    tp_mult: float = 1.5,
    sl_mult: float = 1.5,
    atr_period: int = 14,
) -> pd.DataFrame:
    """
    Возвращает DataFrame с колонками:
      - label     : 1/0 (тронул тейк раньше стопа)
      - tp_pct    : дистанция до тейка (доля цены) на баре входа
      - sl_pct    : дистанция до стопа (доля цены)
    Последние horizon баров получают NaN (будущее неизвестно) и должны быть
    отброшены перед обучением.
    """
    c = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    atrp = _atr_pct(df, atr_period).to_numpy(dtype=float)

    n = len(df)
    label = np.full(n, np.nan)
    tp_arr = np.full(n, np.nan)
    sl_arr = np.full(n, np.nan)

    for t in range(n - horizon):
        a = atrp[t]
        if not np.isfinite(a) or a <= 0:
            continue
        entry = c[t]
        tp = entry * (1 + tp_mult * a)
        sl = entry * (1 - sl_mult * a)
        tp_arr[t] = tp_mult * a
        sl_arr[t] = sl_mult * a

        outcome = 0  # по умолчанию: таймаут или стоп
        for k in range(t + 1, t + horizon + 1):
            hit_tp = high[k] >= tp
            hit_sl = low[k] <= sl
            if hit_tp and hit_sl:
                # оба в одной свече — консервативно считаем, что стоп раньше
                outcome = 0
                break
            if hit_tp:
                outcome = 1
                break
            if hit_sl:
                outcome = 0
                break
        label[t] = outcome

    return pd.DataFrame(
        {"label": label, "tp_pct": tp_arr, "sl_pct": sl_arr}, index=df.index
    )
