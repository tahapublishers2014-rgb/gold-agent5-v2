# -*- coding: utf-8 -*-
"""تولید گزارش بک‌تست GC=F؛ دادهٔ Yahoo عمومی/تأخیری، fills و هزینه‌ها فرضی‌اند."""
import json
import math
import os
import tempfile
import traceback
import urllib.request
from datetime import datetime, timezone

import numpy as np

import gold_agent as ga
import gold_backtest as bt

OUT = "backtest.json"
COST_CASES = {
    "low": {"spread_points": 0.25, "slippage_points_per_side": 0.10,
            "commission_usd_per_contract_side": 1.50, "contract_oz": 100.0},
    "base": dict(bt.DEFAULT_COSTS),
    "stress": {"spread_points": 1.00, "slippage_points_per_side": 0.50,
               "commission_usd_per_contract_side": 4.00, "contract_oz": 100.0},
}


def get_df():
    url = "https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF?range=10y&interval=1d"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            df = ga._parse_chart(json.loads(r.read().decode()))
        if len(df) > 600:
            return df, url
    except Exception as e:
        print("Yahoo chart request failed; using yfinance adapter:", e)
    import yfinance as yf
    df = yf.download("GC=F", period="10y", interval="1d", progress=False, auto_adjust=False)
    if hasattr(df.columns, "droplevel") and getattr(df.columns, "nlevels", 1) > 1:
        df.columns = df.columns.droplevel(1)
    df = df.rename(columns=str.title).dropna(subset=["Close"])
    if len(df) <= 600:
        raise RuntimeError("Yahoo returned too little history for a meaningful test")
    return df, "yfinance:GC=F:10y:1d"


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        v = float(x)
        return v if math.isfinite(v) else None
    return x


def metric_set(df, signals, col, costs, train_end, validation_end):
    bounds = {
        "all": (0, len(df)),
        "train": (0, train_end),
        "validation": (train_end, validation_end),
        "test": (validation_end, len(df)),
    }
    result = {}
    for part, (start, end) in bounds.items():
        segment = bt.apply_cost_model(df, signals, costs=costs, start_i=start, end_i=end)
        result[part] = bt._stats(segment[col])
    return result


def write_atomic(data):
    folder = os.path.dirname(os.path.abspath(OUT))
    fd, tmp = tempfile.mkstemp(prefix="backtest-", suffix=".json", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(clean(data), f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            f.write("\n")
        os.replace(tmp, OUT)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main():
    df, source = get_df()
    # Parameters fixed in advance; no optimization against the final test set.
    horizon, step, warmup, threshold = 5, 3, 260, 25
    signals = bt.generate_signals(df, step=step, warmup=warmup, horizon=horizon, threshold=threshold)
    if len(signals) < 100:
        raise RuntimeError(f"Too few signals: {len(signals)}")
    train_end, validation_end = int(len(df) * 0.60), int(len(df) * 0.80)
    cases = {}
    for name, cost in COST_CASES.items():
        cases[name] = {
            "assumptions": cost,
            "raw": metric_set(df, signals, "r_raw", cost, train_end, validation_end),
            "adjusted": metric_set(df, signals, "r_adj", cost, train_end, validation_end),
        }
    base = cases["base"]["adjusted"]
    test = base["test"]
    train = base["train"]
    if test["n"] < 50:
        verdict = f"فقط {test['n']} معامله در آزمون نهایی وجود دارد؛ نمونه برای قضاوت دربارهٔ راهبرد کافی نیست و نتیجه تأییدنشده است."
    elif test["exp"] is None or test["exp"] <= 0:
        verdict = "در بخش آزمون نهایی، میانگین نتیجه پس از هزینهٔ پایه مثبت نیست؛ سیگنال به‌تنهایی پشتوانهٔ ورود ندارد."
    else:
        stress = cases["stress"]["adjusted"]["test"]
        if stress["exp"] is None or stress["exp"] <= 0:
            verdict = "آزمون نهایی در هزینهٔ پایه مثبت بوده، اما در سناریوی هزینهٔ بالاتر از بین می‌رود؛ راهبرد شکننده و تأییدنشده است."
        elif test["n"] < 100 or train["exp"] is None or train["exp"] <= 0:
            verdict = f"آزمون نهایی پس از هزینه‌ها مثبت است ({test['n']} معامله)، اما آموزش مثبت نبوده یا تعداد آزمون هنوز محدود است؛ نتیجه احتمالاً وابسته به رژیم بازار است و راهبرد تأییدنشده می‌ماند."
        else:
            verdict = "نتیجهٔ آزمون نهایی در سناریوهای هزینهٔ بررسی‌شده مثبت مانده؛ این صرفاً شواهد تاریخی محدود است و پیش‌بینی یا تضمین آینده نیست."
    out = {
        "schema_version": 2,
        "status": "complete",
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": {"provider": "Yahoo Finance", "symbol": "GC=F", "request": source,
                   "interval": "1d", "period_requested": "10y", "instrument_note": "continuous futures proxy; not spot XAU/USD; roll and survivorship limitations apply"},
        "bars": len(df), "points": len(signals), "start": str(df.index[0])[:10], "end": str(df.index[-1])[:10],
        "split": {"train_end_index": train_end, "validation_end_index": validation_end,
                  "train_fraction": 0.60, "validation_fraction": 0.20, "test_fraction": 0.20,
                  "note": "chronological split; test is the final 20%; parameters fixed in code, not tuned on test"},
        "parameters": {"signal": "ga.analyze / gold_pro.adjusted_score computed only through signal close",
                       "entry": "next daily bar open", "stop": "1.5 x ATR(14)", "target": "2R",
                       "max_hold_bars": horizon * 2, "step_bars": step,
                       "same_bar_stop_and_target": "stop first", "overlapping_positions": "skipped per strategy",
                       "risk_fraction_for_equity_curve": 0.01},
        "cost_case_note": "All spread, slippage and commission numbers are explicit illustrative scenarios, not broker quotes. Replace with the user's contract specification and fee schedule.",
        "cost_cases": cases,
        "base_up_fraction": {
            "train": float((signals.loc[signals["i"] < train_end, "fwd"] > 0).mean()),
            "validation": float((signals.loc[(signals["i"] >= train_end) & (signals["i"] < validation_end), "fwd"] > 0).mean()),
            "test": float((signals.loc[signals["i"] >= validation_end, "fwd"] > 0).mean()),
        },
        "verdict": verdict,
        "limitations": ["Yahoo GC=F is a continuous futures proxy, not a broker executable series or spot XAU/USD.",
                        "Roll construction, exact historical contract specification and margin are not guaranteed by Yahoo.",
                        "Daily OHLC cannot resolve intraday event ordering; stop is assumed first when stop and target both touch.",
                        "No broker-specific financing, taxes, market impact or minimum size; cost values are scenarios.",
                        "Metrics are hypothetical and descriptive; no statistical guarantee or live order execution."],
    }
    write_atomic(out)
    print("ok", out["points"], "signals; test trades", test["n"], "verdict:", verdict)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
