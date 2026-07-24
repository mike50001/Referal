"""Генерация признаков (features) из OHLCV для ML-исследования.

ВАЖНО про look-ahead: все признаки на баре t используют данные только
до закрытия бара t включительно (rolling/ewm/shift). Никакого заглядывания
в будущее здесь быть не должно — иначе результаты бэктеста будут фейковыми.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0.0)
    dn = -d.clip(upper=0.0)
    au = up.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    ad = dn.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    rs = au / ad
    out = 100 - 100 / (1 + rs)
    return out.where(ad != 0, 100.0)


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()


# Список колонок-признаков (для обучения) заполняется в make_features.
def make_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Принимает DataFrame с колонками open/high/low/close/volume и DatetimeIndex.
    Возвращает DataFrame признаков, выровненный по индексу (с NaN в начале).
    """
    o, h, l, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]
    f = pd.DataFrame(index=df.index)

    # --- доходности за разные окна (log-return) ---
    logc = np.log(c)
    for n in (1, 3, 6, 12, 24, 48):
        f[f"ret_{n}"] = logc.diff(n)

    # --- отклонение цены от EMA (безразмерное) ---
    for n in (9, 21, 50, 100, 200):
        f[f"ema_dev_{n}"] = c / _ema(c, n) - 1.0

    # --- EMA-кросс (нормированный на цену) ---
    f["ema_cross_9_21"] = (_ema(c, 9) - _ema(c, 21)) / c
    f["ema_cross_21_50"] = (_ema(c, 21) - _ema(c, 50)) / c

    # --- RSI разных периодов ---
    f["rsi_14"] = _rsi(c, 14)
    f["rsi_7"] = _rsi(c, 7)

    # --- волатильность ---
    atr = _atr(df, 14)
    f["atr_pct"] = atr / c
    r1 = logc.diff(1)
    for n in (12, 24, 48):
        f[f"vol_{n}"] = r1.rolling(n).std()

    # --- форма свечи ---
    rng = (h - l).replace(0, np.nan)
    f["body"] = (c - o) / c
    f["upper_wick"] = (h - np.maximum(o, c)) / rng
    f["lower_wick"] = (np.minimum(o, c) - l) / rng
    f["hl_range"] = (h - l) / c

    # --- объём (z-score относительно своего окна) ---
    for n in (24, 96):
        vm = v.rolling(n).mean()
        vs = v.rolling(n).std().replace(0, np.nan)
        f[f"vol_z_{n}"] = (v - vm) / vs

    # --- положение относительно недавних экстремумов ---
    for n in (24, 96):
        f[f"pos_high_{n}"] = c / h.rolling(n).max() - 1.0
        f[f"pos_low_{n}"] = c / l.rolling(n).min() - 1.0

    # --- время (циклически) ---
    idx = df.index
    hour = idx.hour + idx.minute / 60.0
    f["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    f["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    f["dow_sin"] = np.sin(2 * np.pi * idx.dayofweek / 7)
    f["dow_cos"] = np.cos(2 * np.pi * idx.dayofweek / 7)

    return f


def feature_columns(f: pd.DataFrame) -> list[str]:
    return list(f.columns)
