# -*- coding: utf-8 -*-
"""
سبک‌های تکمیلی: امواج الیوت، الگوهای هارمونیک، ولیوم‌پروفایل، پارابولیک SAR
خروجی هر سبک مثل gold_styles.py: (vote, alerts)

توجه: الیوت و هارمونیک ذاتاً تفسیری‌اند. این‌جا فقط نسخه‌ی قاعده‌مند و ساده‌ی آن‌ها پیاده شده
(بر پایه‌ی زیگ‌زاگ ATR) و اطمینانشان کمتر از سبک‌های دیگر است.
"""
import numpy as np
import pandas as pd

from gold_styles import _pivots


def zigzag(df, mult=1.5, lookback=250):
    """زیگ‌زاگ بر پایه‌ی پیوت‌ها؛ حرکت‌های کوچک‌تر از mult×ATR نادیده گرفته می‌شوند."""
    sub = df.iloc[-lookback:]
    h, l = sub["High"].values, sub["Low"].values
    atr = df["atr"].iloc[-1]
    hi, _ = _pivots(h, 3)
    _, lo = _pivots(l, 3)
    cands = sorted([(i, h[i], "H") for i in hi] + [(i, l[i], "L") for i in lo], key=lambda x: x[0])
    pts = []
    for i, p, t in cands:
        if not pts:
            pts.append((i, p, t))
            continue
        li, lp, lt = pts[-1]
        if t == lt:
            if (t == "H" and p > lp) or (t == "L" and p < lp):
                pts[-1] = (i, p, t)
        elif abs(p - lp) >= mult * atr:
            pts.append((i, p, t))
    return pts, len(sub)


# ------------------------------------------------------------ امواج الیوت
def _valid_impulse(p, s, full):
    w1, w3 = s * (p[1] - p[0]), s * (p[3] - p[2])
    if w1 <= 0 or w3 <= 0:
        return False
    if s * (p[2] - p[0]) <= 0:      # موج ۲ نباید کل موج ۱ را پس بگیرد
        return False
    if s * (p[3] - p[1]) <= 0:      # موج ۳ باید از انتهای موج ۱ عبور کند
        return False
    if s * (p[4] - p[1]) <= 0:      # موج ۴ نباید وارد محدوده‌ی موج ۱ شود
        return False
    if full:
        w5 = s * (p[5] - p[4])
        if w5 <= 0 or s * (p[5] - p[3]) <= 0:
            return False
        if w3 < w1 and w3 < w5:     # موج ۳ نباید کوتاه‌ترین باشد
            return False
    elif w3 < w1:
        return False
    return True


def elliott(df):
    if len(df) < 120:
        return None, []
    pts, n = zigzag(df)
    if len(pts) < 3:
        return 0, []
    price = df["Close"].iloc[-1]
    a, v, done = [], 0, False
    last_recent = n - 1 - pts[-1][0]

    if len(pts) >= 6 and last_recent <= 30:
        seg = pts[-6:]
        for s, t0 in ((1, "L"), (-1, "H")):
            if seg[0][2] == t0 and _valid_impulse([x[1] for x in seg], s, True):
                if s == 1:
                    a.append(("warn", "w5_done_up", f"الگوی ۵ موجی صعودی احتمالاً کامل شده (موج ۵ نزدیک {seg[5][1]:,.0f}); ریسک اصلاح ABC. شمارش الیوت ذهنی است"))
                else:
                    a.append(("warn", "w5_done_dn", f"الگوی ۵ موجی نزولی احتمالاً کامل شده (موج ۵ نزدیک {seg[5][1]:,.0f}); احتمال برگشت یا اصلاح صعودی. شمارش الیوت ذهنی است"))
                done = True
                break

    if not done and len(pts) >= 5 and last_recent <= 40:
        seg = pts[-5:]
        p = [x[1] for x in seg]
        for s, t0 in ((1, "L"), (-1, "H")):
            if seg[0][2] == t0 and _valid_impulse(p, s, False) and s * (price - p[4]) > 0:
                target = p[4] + s * (p[1] - p[0])
                if s == 1:
                    a.append(("good", "w5_up", f"احتمالاً در موج ۵ صعودی (الیوت، اطمینان کم)؛ هدف تقریبی {target:,.0f}، ابطال با شکست {p[4]:,.0f}"))
                else:
                    a.append(("bad", "w5_dn", f"احتمالاً در موج ۵ نزولی (الیوت، اطمینان کم)؛ هدف تقریبی {target:,.0f}، ابطال با شکست {p[4]:,.0f}"))
                v = s
                done = True
                break

    if not done and len(pts) >= 3 and last_recent <= 25:
        seg = pts[-3:]
        p0, p1, p2 = (x[1] for x in seg)
        for s, t0 in ((1, "L"), (-1, "H")):
            w1 = s * (p1 - p0)
            if seg[0][2] == t0 and w1 > 0:
                ret = s * (p1 - p2) / w1
                if 0.382 <= ret <= 0.786 and s * (price - p2) > 0:
                    target = p2 + s * 1.618 * w1
                    if s == 1:
                        a.append(("good", "w3_up", f"احتمال شروع موج ۳ صعودی (موج ۲ به {ret:.2f} موج ۱ برگشته)؛ هدف تقریبی {target:,.0f}، ابطال زیر {p0:,.0f}"))
                    else:
                        a.append(("bad", "w3_dn", f"احتمال شروع موج ۳ نزولی (موج ۲ به {ret:.2f} موج ۱ برگشته)؛ هدف تقریبی {target:,.0f}، ابطال بالای {p0:,.0f}"))
                    v = s
                    break
    return v, a


# ---------------------------------------------------------------- هارمونیک
PATTERNS = [
    ("گارتلی", (0.568, 0.668), (0.736, 0.836)),
    ("بت", (0.332, 0.55), (0.836, 0.936)),
    ("پروانه", (0.736, 0.836), (1.22, 1.67)),
    ("خرچنگ", (0.332, 0.668), (1.568, 1.668)),
]


def _check_xabcd(X, A, B, C, D):
    s = 1 if A > X else -1
    if not (s * (A - X) > 0 and s * (A - B) > 0 and s * (B - X) > 0 and
            s * (C - B) > 0 and s * (A - C) > 0 and s * (C - D) > 0):
        return None
    xa, ab, bc = abs(A - X), abs(A - B), abs(C - B)
    if xa == 0 or ab == 0:
        return None
    rb, rc, ad = ab / xa, bc / ab, s * (A - D) / xa
    if not (0.35 <= rc <= 0.92):
        return None
    for name, (b0, b1), (d0, d1) in PATTERNS:
        if b0 <= rb <= b1 and d0 <= ad <= d1:
            return name, s, ad
    return None


def harmonic(df):
    if len(df) < 60:
        return None, []
    pts, n = zigzag(df, mult=1.0)
    price = df["Close"].iloc[-1]
    found = None
    if len(pts) >= 5 and n - 1 - pts[-1][0] <= 8:
        X, A, B, C, D = [p for _, p, _ in pts[-5:]]
        found = _check_xabcd(X, A, B, C, D)
    if not found and len(pts) >= 4 and n - 1 - pts[-1][0] <= 40:
        X, A, B, C = [p for _, p, _ in pts[-4:]]
        found = _check_xabcd(X, A, B, C, price)
    if not found:
        return 0, []
    name, s, ad = found
    if s == 1:
        return 1, [("good", "bull", f"الگوی هارمونیک {name} صعودی: قیمت در ناحیه‌ی برگشت بالقوه (PRZ، AD={ad:.3f} از XA)؛ منتظر تأیید کندلی بمان")]
    return -1, [("bad", "bear", f"الگوی هارمونیک {name} نزولی: قیمت در ناحیه‌ی برگشت بالقوه (PRZ، AD={ad:.3f} از XA)؛ منتظر تأیید کندلی بمان")]


# --------------------------------------------------------- ولیوم‌پروفایل
def volume_profile(df, bars=100, bins=30):
    if df["Volume"].tail(50).mean() <= 0 or len(df) < bars:
        return None, []
    sub = df.iloc[-bars:]
    lo, hi = sub["Low"].min(), sub["High"].max()
    if hi <= lo:
        return None, []
    edges = np.linspace(lo, hi, bins + 1)
    vol = np.zeros(bins)
    for h, l, v in zip(sub["High"].values, sub["Low"].values, sub["Volume"].values):
        i0 = min(bins - 1, max(0, np.searchsorted(edges, l, side="right") - 1))
        i1 = min(bins - 1, max(0, np.searchsorted(edges, h, side="right") - 1))
        vol[i0:i1 + 1] += v / (i1 - i0 + 1)
    poc = int(vol.argmax())
    total, acc, lo_i, hi_i = vol.sum(), vol[poc], poc, poc
    while acc < 0.7 * total and (lo_i > 0 or hi_i < bins - 1):
        up = vol[hi_i + 1] if hi_i < bins - 1 else -1
        dn = vol[lo_i - 1] if lo_i > 0 else -1
        if up >= dn:
            hi_i += 1
            acc += vol[hi_i]
        else:
            lo_i -= 1
            acc += vol[lo_i]
    val, vah, poc_p = edges[lo_i], edges[hi_i + 1], (edges[poc] + edges[poc + 1]) / 2
    price, atr = df["Close"].iloc[-1], df["atr"].iloc[-1]
    a = []
    if price > vah:
        a.append(("good", "above", f"قیمت بالای ناحیه‌ی ارزش (VAH={vah:,.1f}); پذیرش قیمت‌های بالاتر"))
        vote = 1
    elif price < val:
        a.append(("bad", "below", f"قیمت زیر ناحیه‌ی ارزش (VAL={val:,.1f}); پذیرش قیمت‌های پایین‌تر"))
        vote = -1
    else:
        a.append(("info", "inside", f"قیمت داخل ناحیه‌ی ارزش {val:,.1f}–{vah:,.1f}"))
        vote = 0
    if abs(price - poc_p) < 0.3 * atr:
        a.append(("info", "poc", f"قیمت روی POC ({poc_p:,.1f}) است؛ پرحجم‌ترین سطح و آهنربای قیمت"))
    return vote, a


# ------------------------------------------------------- پارابولیک SAR
def psar(df, af0=0.02, afmax=0.2):
    if len(df) < 40:
        return None, []
    h, l = df["High"].values, df["Low"].values
    n = len(h)
    sar, trend = np.zeros(n), np.ones(n)
    bull, ep, af = True, h[0], af0
    sar[0] = l[0]
    for i in range(1, n):
        s = sar[i - 1] + af * (ep - sar[i - 1])
        if bull:
            s = min(s, l[i - 1], l[i - 2] if i > 1 else l[i - 1])
            if l[i] < s:
                bull, s, ep, af = False, ep, l[i], af0
            elif h[i] > ep:
                ep, af = h[i], min(af + af0, afmax)
        else:
            s = max(s, h[i - 1], h[i - 2] if i > 1 else h[i - 1])
            if h[i] > s:
                bull, s, ep, af = True, ep, h[i], af0
            elif l[i] < ep:
                ep, af = l[i], min(af + af0, afmax)
        sar[i], trend[i] = s, (1 if bull else -1)
    a = []
    if trend[-1] != trend[-3]:
        a.append(("good" if trend[-1] == 1 else "bad", "flip", "پارابولیک SAR به " + ("صعودی" if trend[-1] == 1 else "نزولی") + f" برگشت (نقطه {sar[-1]:,.1f})"))
    return int(trend[-1]), a


EXTRA = [
    ("الیوت", elliott),
    ("هارمونیک", harmonic),
    ("ولیوم‌پروفایل", volume_profile),
    ("پارابولیک SAR", psar),
]


def run_extra(df):
    votes, alerts = {}, []
    for name, fn in EXTRA:
        try:
            v, al = fn(df)
        except Exception:
            continue
        if v is None:
            continue
        votes[name] = v
        for lvl, key, txt in al:
            alerts.append((lvl, f"{name}:{key}", f"[{name}] {txt}"))
    return votes, alerts
