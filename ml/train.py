"""Обучение и ЧЕСТНАЯ проверка ML-модели (LightGBM) на истории.

Пайплайн:
  1. Загружаем CSV со свечами (из ml/fetch_data.py).
  2. Строим признаки (ml/features) и метки тройного барьера (ml/labels).
  3. Walk-forward валидация: несколько последовательных фолдов «обучение в
     прошлом -> тест в будущем», с разрывом (purge/embargo) = horizon, чтобы
     метки train не пересекались с test (защита от утечки будущего).
  4. На каждом тест-фолде считаем метрики и «бэктест по меткам» с комиссиями.
  5. Печатаем честный итог и сравнение с базовой ставкой (доля лонг-побед).

Запуск:
    python -m ml.train --csv ml/data/BTCUSDT_1h.csv --horizon 12 --tp 1.5 --sl 1.5
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import make_features  # noqa: E402
from labels import triple_barrier_labels  # noqa: E402

try:
    import lightgbm as lgb
    from sklearn.metrics import roc_auc_score
except ImportError:
    print("Нужны пакеты: pip install -r ml/requirements-ml.txt", file=sys.stderr)
    raise


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    need = {"open", "high", "low", "close", "volume"}
    if not need.issubset(df.columns):
        raise ValueError(f"CSV должен содержать колонки {need}")
    return df


def walk_forward_splits(n: int, n_folds: int, embargo: int):
    """Расширяющееся окно: train=[0..s), test=[s+embargo..e). Возвращает пары."""
    fold = n // (n_folds + 1)
    for i in range(1, n_folds + 1):
        train_end = fold * i
        test_start = train_end + embargo
        test_end = min(fold * (i + 1), n)
        if test_start >= test_end:
            continue
        yield np.arange(0, train_end), np.arange(test_start, test_end)


def main() -> None:
    p = argparse.ArgumentParser(description="ML walk-forward обучение и бэктест")
    p.add_argument("--csv", required=True)
    p.add_argument("--horizon", type=int, default=12, help="горизонт разметки (баров)")
    p.add_argument("--tp", type=float, default=1.5, help="тейк в ATR")
    p.add_argument("--sl", type=float, default=1.5, help="стоп в ATR")
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--threshold", type=float, default=0.55, help="порог вероятности для входа")
    p.add_argument("--fee", type=float, default=0.0004, help="комиссия на сторону (0.04%% по умолч.)")
    args = p.parse_args()

    df = load_csv(args.csv)
    print(f"Загружено {len(df)} свечей: {df.index[0]} .. {df.index[-1]}")

    feats = make_features(df)
    lab = triple_barrier_labels(df, args.horizon, args.tp, args.sl)

    data = feats.join(lab)
    data = data.replace([np.inf, -np.inf], np.nan).dropna()
    feat_cols = list(feats.columns)
    X = data[feat_cols]
    y = data["label"].astype(int)
    tp_pct = data["tp_pct"].to_numpy()
    sl_pct = data["sl_pct"].to_numpy()

    base_rate = y.mean()
    print(f"Готово примеров: {len(y)} | базовая доля лонг-побед: {base_rate:.3f}")
    print(f"Признаков: {len(feat_cols)} | горизонт={args.horizon} tp={args.tp}ATR sl={args.sl}ATR")
    print("=" * 64)

    params = dict(
        objective="binary", n_estimators=300, learning_rate=0.03,
        num_leaves=31, max_depth=-1, subsample=0.8, colsample_bytree=0.8,
        reg_lambda=1.0, min_child_samples=50, n_jobs=-1, verbosity=-1,
    )

    aucs, accs, trade_pnls, trade_counts, win_rates = [], [], [], [], []
    fee_roundtrip = 2 * args.fee

    for fold, (tr, te) in enumerate(walk_forward_splits(len(X), args.folds, args.horizon), 1):
        Xtr, ytr = X.iloc[tr], y.iloc[tr]
        Xte, yte = X.iloc[te], y.iloc[te]
        if ytr.nunique() < 2 or len(yte) == 0:
            continue

        model = lgb.LGBMClassifier(**params)
        model.fit(Xtr, ytr)
        proba = model.predict_proba(Xte)[:, 1]

        try:
            auc = roc_auc_score(yte, proba)
        except ValueError:
            auc = float("nan")
        pred = (proba >= args.threshold).astype(int)
        acc = (pred == yte.to_numpy()).mean()

        # Бэктест «по меткам»: входим в лонг, где модель уверена.
        enter = pred == 1
        n_trades = int(enter.sum())
        if n_trades:
            outcomes = yte.to_numpy()[enter]           # 1=тейк, 0=стоп
            tps = tp_pct[te][enter]
            sls = sl_pct[te][enter]
            # доходность сделки в долях: +tp при победе, -sl при поражении, минус комиссии
            pnl = np.where(outcomes == 1, tps, -sls) - fee_roundtrip
            fold_pnl = pnl.sum()
            wr = outcomes.mean()
        else:
            fold_pnl, wr = 0.0, float("nan")

        aucs.append(auc)
        accs.append(acc)
        trade_pnls.append(fold_pnl)
        trade_counts.append(n_trades)
        win_rates.append(wr)

        print(f"Фолд {fold}: train={len(tr):6d} test={len(te):6d} | "
              f"AUC={auc:.3f} acc={acc:.3f} | сделок={n_trades:4d} "
              f"winrate={wr:.3f} PnL={fold_pnl:+.3f}R")

    print("=" * 64)
    mean_auc = np.nanmean(aucs) if aucs else float("nan")
    total_pnl = float(np.nansum(trade_pnls))
    total_trades = int(np.nansum(trade_counts))
    mean_wr = np.nanmean(win_rates) if win_rates else float("nan")
    print(f"ИТОГ: средний AUC={mean_auc:.3f} (0.5 = бесполезно, монетка)")
    print(f"      всего сделок={total_trades}  средний winrate={mean_wr:.3f}")
    print(f"      суммарный PnL (после комиссий)={total_pnl:+.3f}R")
    print("=" * 64)

    # Честная интерпретация.
    print("\nКАК ЧИТАТЬ РЕЗУЛЬТАТ (честно):")
    if not np.isfinite(mean_auc) or mean_auc <= 0.52:
        print("  • AUC ~0.5 -> модель НЕ отличает прибыльные сделки от убыточных.")
        print("    Устойчивого edge нет. Это норма для простых фич на крипте.")
    elif mean_auc < 0.55:
        print("  • AUC чуть выше 0.5 -> слабый сигнал. Легко съедается комиссиями/")
        print("    проскальзыванием. Нужны честные проверки, прежде чем верить.")
    else:
        print("  • AUC заметно выше 0.5 -> есть на что посмотреть. НО: проверь на")
        print("    других периодах/символах, увеличь комиссию, ищи утечки данных.")
    if total_pnl <= 0:
        print("  • Суммарный PnL <= 0 после комиссий -> на этих настройках не зарабатывает.")
    print("  • Один хороший прогон != рабочая стратегия. Нужны out-of-sample,")
    print("    разные рынки, forward-тест на testnet МЕСЯЦАМИ, и лишь потом деньги.")


if __name__ == "__main__":
    main()
