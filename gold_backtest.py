# -*- coding: utf-8 -*-
"""بک‌تست فرضی GC=F با سیگنال در close و ورود در open کندل بعدی.
هزینه‌ها سناریویی‌اند؛ داده Yahoo پیوسته و جانشین تقریبی قرارداد اجرایی است.
"""
import math

import numpy as np
import pandas as pd

import gold_agent as ga
import gold_pro as gp

DEFAULT_COSTS = {
    "spread_points": 0.50,                 # فرض سناریویی، دلار به‌ازای هر اونس برای رفت‌وبرگشت
    "slippage_points_per_side": 0.25,       # فرض سناریویی، دلار به‌ازای هر اونس در هر سمت
    "commission_usd_per_contract_side": 2.50,
    "contract_oz": 100.0,
}


def generate_signals(df, step=3, warmup=260, horizon=5, threshold=25):
    """محاسبهٔ ویژگی‌ها فقط از کندل‌های موجود تا زمان سیگنال؛ بدون استفاده از آینده."""
    required = {"Open", "High", "Low", "Close"}
    if not required.issubset(df.columns):
        raise ValueError("OHLC data must include Open, High, Low, Close")
    if step < 1 or horizon < 1 or len(df) <= warmup + horizon:
        raise ValueError("Insufficient data or invalid step/horizon")
    rows = []
    for i in range(warmup, len(df) - horizon - 1, step):
        sub = df.iloc[:i + 1]
        rep = ga.analyze(sub, "1d")
        reg = gp.regime(sub)
        adj = gp.adjusted_score(rep, reg["kind"])
        fwd = float(df["Close"].iloc[i + horizon] / df["Close"].iloc[i] - 1)
        rows.append({
            "i": int(i), "timestamp": str(df.index[i]),
            "score": int(rep["score"]), "adj": int(adj),
            "atr": float(rep["atr"]), "fwd": fwd,
            "regime": reg["kind"], "votes": rep["votes"],
            "side_raw": 1 if rep["score"] >= threshold else -1 if rep["score"] <= -threshold else 0,
            "side_adj": 1 if adj >= threshold else -1 if adj <= -threshold else 0,
        })
    return pd.DataFrame(rows)


def simulate(df, i, side, atr, max_bars, costs=None, rr=2.0, sl_mult=1.5):
    """اجرای فرضی پس از سیگنال close[i]، در open[i+1]. حد و هدف داخل یک کندل: حدضرر اول."""
    costs = dict(DEFAULT_COSTS if costs is None else costs)
    entry_i = i + 1
    if entry_i >= len(df) or not np.isfinite(atr) or atr <= 0:
        return None
    contract_oz = float(costs.get("contract_oz", 100.0))
    if contract_oz <= 0:
        raise ValueError("contract_oz must be positive")
    half_spread_and_slip = max(0.0, float(costs.get("spread_points", 0.0))) / 2 + max(0.0, float(costs.get("slippage_points_per_side", 0.0)))
    commission_points = 2 * max(0.0, float(costs.get("commission_usd_per_contract_side", 0.0))) / contract_oz
    entry_mid = float(df["Open"].iloc[entry_i])
    entry = entry_mid + side * half_spread_and_slip
    risk_points = sl_mult * float(atr)
    stop = entry - side * risk_points
    target = entry + side * rr * risk_points
    last_i = min(entry_i + max_bars - 1, len(df) - 1)
    for j in range(entry_i, last_i + 1):
        op = float(df["Open"].iloc[j]); hi = float(df["High"].iloc[j]); lo = float(df["Low"].iloc[j])
        hit_sl = lo <= stop if side > 0 else hi >= stop
        hit_tp = hi >= target if side > 0 else lo <= target
        if hit_sl:  # در صورت لمس هم‌زمان، فرض محافظه‌کارانه: stop اول
            base_exit = min(op, stop) if side > 0 else max(op, stop)
            reason = "stop"
        elif hit_tp:
            base_exit = target
            reason = "target"
        else:
            continue
        exit_price = base_exit - side * half_spread_and_slip
        gross_points = side * (exit_price - entry)
        net_r = (gross_points - commission_points) / risk_points
        return {"signal_i": i, "entry_i": entry_i, "exit_i": j, "entry": entry,
                "exit": exit_price, "stop": stop, "target": target,
                "gross_r": gross_points / risk_points, "net_r": net_r,
                "cost_r": (2 * half_spread_and_slip + commission_points) / risk_points,
                "exit_reason": reason}
    base_exit = float(df["Close"].iloc[last_i])
    exit_price = base_exit - side * half_spread_and_slip
    gross_points = side * (exit_price - entry)
    return {"signal_i": i, "entry_i": entry_i, "exit_i": last_i, "entry": entry,
            "exit": exit_price, "stop": stop, "target": target,
            "gross_r": gross_points / risk_points,
            "net_r": (gross_points - commission_points) / risk_points,
            "cost_r": (2 * half_spread_and_slip + commission_points) / risk_points,
            "exit_reason": "time"}


def apply_cost_model(df, signals, costs=None, horizon=5, max_hold=None, start_i=0, end_i=None):
    """اعمال همان سیگنال‌ها با یک مدل هزینه؛ یک پوزیشن برای هر روش، بدون هم‌پوشانی."""
    costs = dict(DEFAULT_COSTS if costs is None else costs)
    max_hold = int(max_hold or horizon * 2)
    end_i = len(df) if end_i is None else min(int(end_i), len(df))
    out = signals[(signals["i"] >= int(start_i)) & (signals["i"] < end_i)].copy()
    for method in ("raw", "adj"):
        trades, last_exit = [], -1
        for row in out.to_dict("records"):
            i, side = int(row["i"]), int(row["side_" + method])
            if side == 0 or i < last_exit or i + 1 >= end_i:
                continue
            bounded_hold = min(max_hold, end_i - (i + 1))
            trade = simulate(df, i, side, row["atr"], bounded_hold, costs=costs)
            if trade is not None:
                trades.append(trade)
                last_exit = trade["exit_i"]
        by_signal = {t["signal_i"]: t for t in trades}
        out["r_" + method] = [by_signal.get(int(i), {}).get("net_r", np.nan) for i in out["i"]]
        out["trade_" + method] = [by_signal.get(int(i)) for i in out["i"]]
    return out


def run(df, horizon=5, step=3, warmup=260, thr=25, costs=None, verbose=False):
    signals = generate_signals(df, step=step, warmup=warmup, horizon=horizon, threshold=thr)
    return apply_cost_model(df, signals, costs=costs, horizon=horizon)


def _stats(r, risk_fraction=0.01):
    """آمار توصیفی بر حسب R؛ بازده حساب صرفاً فرضی با ریسک ثابت ۱٪ در هر معامله."""
    r = pd.to_numeric(pd.Series(r), errors="coerce").dropna()
    if r.empty:
        return {"n": 0, "win": None, "exp": None, "pf": None, "max_dd_pct": None,
                "total_r": None, "equity_return_pct": None}
    vals = r.to_numpy(dtype=float)
    wins, losses = vals[vals > 0].sum(), -vals[vals < 0].sum()
    factors = np.maximum(1 + vals * risk_fraction, 1e-9)
    equity = np.cumprod(factors)
    peaks = np.maximum.accumulate(np.r_[1.0, equity])[1:]
    dd = (peaks - equity) / peaks
    return {"n": int(len(vals)), "win": float(np.mean(vals > 0)),
            "exp": float(np.mean(vals)), "pf": float(wins / losses) if losses > 0 else None,
            "max_dd_pct": float(np.max(dd)) if len(dd) else 0.0,
            "total_r": float(np.sum(vals)),
            "equity_return_pct": float((equity[-1] - 1) * 100),
            "risk_fraction_per_trade": float(risk_fraction)}


def report(res, label=""):
    """گزارش متنی برای اجرای مستقیم و محلی."""
    out = [f"\n===== بک‌تست فرضی {label}: {len(res)} سیگنال ====="]
    out.append("ورود در بازشدن کندل بعد از سیگنال؛ هزینه‌ها و fills فرضی‌اند؛ سیگنال‌های هم‌پوشان حذف شده‌اند.")
    for name, col in (("خام", "r_raw"), ("تعدیل‌شده", "r_adj")):
        s = _stats(res[col])
        out.append(f"{name}: n={s['n']}, win={s['win']}, exp_R={s['exp']}, PF={s['pf']}, maxDD={s['max_dd_pct']}")
    out.append("این نتایج بر دادهٔ تاریخی GC=F و مفروضات هزینه‌ای مشخص‌شده تکیه دارند؛ سود آینده را پیش‌بینی یا تضمین نمی‌کنند.")
    return "\n".join(out)
