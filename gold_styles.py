# -*- coding: utf-8 -*-
"""
ماژول سبک‌های تحلیلی برای gold_agent.py
هر سبک (vote, alerts) برمی‌گرداند:  vote: +1 صعودی / -1 نزولی / 0 خنثی / None یعنی داده‌ی لازم نیست
alerts: لیست (level, key, text) با level یکی از good / bad / warn / info
ورودی: دیتافریم OHLCV که اندیکاتورهای پایه (atr و ...) روی آن محاسبه شده است.
"""
import numpy as np
import pandas as pd


def _pivots(v, w):
    hi, lo = [], []
    for i in range(w, len(v) - w):
        win = v[i - w:i + w + 1]
        if v[i] == win.max():
            hi.append(i)
        if v[i] == win.min():
            lo.append(i)
    return hi, lo


def _sign(x):
    return 1 if x > 0 else -1 if x < 0 else 0


# ------------------------------------------------------------ ایچیموکو
def ichimoku(df):
    if len(df) < 90:
        return None, []
    h, l, c = df["High"], df["Low"], df["Close"]
    t = (h.rolling(9).max() + l.rolling(9).min()) / 2
    k = (h.rolling(26).max() + l.rolling(26).min()) / 2
    sa = (t + k) / 2
    sb = (h.rolling(52).max() + l.rolling(52).min()) / 2
    ca, cb = sa.shift(26), sb.shift(26)
    top, bot = max(ca.iloc[-1], cb.iloc[-1]), min(ca.iloc[-1], cb.iloc[-1])
    if np.isnan(top) or np.isnan(t.iloc[-1]) or np.isnan(k.iloc[-1]):
        return None, []
    price = c.iloc[-1]
    above, below = price > top, price < bot
    tk_up = t.iloc[-1] > k.iloc[-1]
    a = []
    vote = 1 if (above and tk_up) else -1 if (below and not tk_up) else 0

    prev_up = t.iloc[-3] > k.iloc[-3]
    if tk_up and not prev_up:
        a.append(("good" if above else "warn", "tk_up",
                  "کراس صعودی تنکان/کیجون" + (" بالای ابر (قوی)" if above else " زیر/داخل ابر (ضعیف)")))
    if (not tk_up) and prev_up:
        a.append(("bad" if below else "warn", "tk_dn",
                  "کراس نزولی تنکان/کیجون" + (" زیر ابر (قوی)" if below else " بالا/داخل ابر (ضعیف)")))
    ptop, pbot = max(ca.iloc[-4], cb.iloc[-4]), min(ca.iloc[-4], cb.iloc[-4])
    if above and c.iloc[-4] <= ptop:
        a.append(("good", "cloud_up", "خروج صعودی قیمت از ابر کومو"))
    if below and c.iloc[-4] >= pbot:
        a.append(("bad", "cloud_dn", "خروج نزولی قیمت از ابر کومو"))
    if bot <= price <= top:
        a.append(("warn", "in_cloud", "قیمت داخل ابر است؛ بازار بدون جهت و سیگنال‌ها کم‌اعتبار"))
    fut_up, prev_fut = sa.iloc[-1] > sb.iloc[-1], sa.iloc[-4] > sb.iloc[-4]
    if fut_up != prev_fut:
        a.append(("good" if fut_up else "bad", "twist", "تغییر رنگ ابر آینده (کومو توئیست) به " + ("صعودی" if fut_up else "نزولی")))
    if len(c) > 27:
        chik_up = price > c.iloc[-27]
        a.append(("info", "chikou", "چیکو اسپن " + ("بالای قیمت ۲۶ کندل قبل (تأیید صعود)" if chik_up else "زیر قیمت ۲۶ کندل قبل (تأیید نزول)")))
    return vote, a


# -------------------------------------------------------- اسمارت مانی (SMC)
def smc(df):
    n = len(df)
    if n < 60:
        return None, []
    h, l, c, o = (df[x].values for x in ("High", "Low", "Close", "Open"))
    atr_s = df["atr"].values
    atr, price = atr_s[-1], c[-1]
    hi, _ = _pivots(h, 3)
    _, lo = _pivots(l, 3)
    a, v = [], 0

    trend = 0
    if len(hi) >= 2 and len(lo) >= 2:
        hh, hl = h[hi[-1]] > h[hi[-2]], l[lo[-1]] > l[lo[-2]]
        if hh and hl:
            trend = 1
        elif (not hh) and (not hl):
            trend = -1
    v += trend
    a.append(("info", "struct", "ساختار بازار: " + {1: "صعودی (HH/HL)", -1: "نزولی (LH/LL)", 0: "رنج یا مبهم"}[trend]))

    if hi and lo:
        sh, sl = h[hi[-1]], l[lo[-1]]
        # BOS / CHoCH
        if c[-1] > sh and c[-4] <= sh:
            if trend == -1:
                a.append(("good", "choch_up", f"CHoCH صعودی: شکست {sh:,.1f} در ساختار نزولی؛ اولین نشانه‌ی تغییر روند"))
            else:
                a.append(("good", "bos_up", f"BOS صعودی: شکست {sh:,.1f}؛ تداوم روند"))
            v += 1
        elif c[-1] < sl and c[-4] >= sl:
            if trend == 1:
                a.append(("bad", "choch_dn", f"CHoCH نزولی: شکست {sl:,.1f} در ساختار صعودی؛ اولین نشانه‌ی تغییر روند"))
            else:
                a.append(("bad", "bos_dn", f"BOS نزولی: شکست {sl:,.1f}؛ تداوم روند"))
            v -= 1
        # Sweep نقدینگی
        for b in (-1, -2):
            if h[b] > sh and c[b] < sh:
                a.append(("bad", "sweep_hi", f"جمع‌آوری نقدینگی بالای سقف {sh:,.1f} و بازگشت (Sweep)؛ شکار استاپ خریداران"))
                v -= 1
                break
            if l[b] < sl and c[b] > sl:
                a.append(("good", "sweep_lo", f"جمع‌آوری نقدینگی زیر کف {sl:,.1f} و بازگشت (Sweep)؛ شکار استاپ فروشندگان"))
                v += 1
                break
        # Premium / Discount
        if sh > sl:
            pos = (price - sl) / (sh - sl)
            if 0 <= pos <= 1:
                zone = "پریمیوم (گران)" if pos > 0.5 else "دیسکانت (ارزان)"
                note = ""
                if trend == 1 and pos < 0.5:
                    note = " | در روند صعودی، ناحیه‌ی ترجیحی خرید در SMC"
                if trend == -1 and pos > 0.5:
                    note = " | در روند نزولی، ناحیه‌ی ترجیحی فروش در SMC"
                a.append(("info", "pd", f"قیمت در ناحیه {zone} رنج {sl:,.0f}–{sh:,.0f}{note}"))

    # سقف/کف برابر = استخر نقدینگی
    if len(hi) >= 2 and abs(h[hi[-1]] - h[hi[-2]]) < 0.2 * atr:
        a.append(("info", "eqh", f"سقف‌های برابر نزدیک {h[hi[-1]]:,.1f}: نقدینگی بالا و هدف جمع‌آوری استاپ"))
    if len(lo) >= 2 and abs(l[lo[-1]] - l[lo[-2]]) < 0.2 * atr:
        a.append(("info", "eql", f"کف‌های برابر نزدیک {l[lo[-1]]:,.1f}: نقدینگی پایین و هدف جمع‌آوری استاپ"))

    # FVG پرنشده
    bull = bear = None
    for i in range(max(2, n - 40), n):
        if l[i] > h[i - 2] and (l[i] - h[i - 2]) > 0.3 * atr:
            bot_, top_ = h[i - 2], l[i]
            if i == n - 1 or l[i + 1:].min() > bot_:
                bull = (bot_, top_)
        if h[i] < l[i - 2] and (l[i - 2] - h[i]) > 0.3 * atr:
            bot_, top_ = h[i], l[i - 2]
            if i == n - 1 or h[i + 1:].max() < top_:
                bear = (bot_, top_)
    if bull and bull[0] - 0.1 * atr <= price <= bull[1] + 0.3 * atr:
        a.append(("good", "fvg_bull", f"قیمت در/نزدیک FVG صعودی {bull[0]:,.1f}–{bull[1]:,.1f}؛ حمایت بالقوه"))
        v += 1
    if bear and bear[0] - 0.3 * atr <= price <= bear[1] + 0.1 * atr:
        a.append(("bad", "fvg_bear", f"قیمت در/نزدیک FVG نزولی {bear[0]:,.1f}–{bear[1]:,.1f}؛ مقاومت بالقوه"))
        v -= 1

    # Order Block
    ob_bull = ob_bear = None
    for i in range(max(1, n - 50), n - 1):
        body = c[i] - o[i]
        if body > 1.5 * atr_s[i]:
            for j in range(i - 1, max(i - 6, 0), -1):
                if c[j] < o[j]:
                    ob_bull = (i, l[j], h[j])
                    break
        elif -body > 1.5 * atr_s[i]:
            for j in range(i - 1, max(i - 6, 0), -1):
                if c[j] > o[j]:
                    ob_bear = (i, l[j], h[j])
                    break
    if ob_bull and c[ob_bull[0]:].min() >= ob_bull[1] and ob_bull[1] <= price <= ob_bull[2] + 0.3 * atr:
        a.append(("good", "ob_bull", f"قیمت در بلوک سفارش صعودی {ob_bull[1]:,.1f}–{ob_bull[2]:,.1f}؛ ناحیه‌ی ورود نهادی بالقوه"))
        v += 1
    if ob_bear and c[ob_bear[0]:].max() <= ob_bear[2] and ob_bear[1] - 0.3 * atr <= price <= ob_bear[2]:
        a.append(("bad", "ob_bear", f"قیمت در بلوک سفارش نزولی {ob_bear[1]:,.1f}–{ob_bear[2]:,.1f}؛ ناحیه‌ی فروش نهادی بالقوه"))
        v -= 1
    return _sign(v), a


# ---------------------------------------------- الگوهای نموداری (پرایس‌اکشن)
def patterns(df):
    sub = df.iloc[-90:]
    if len(sub) < 40:
        return None, []
    c = sub["Close"].values
    n, price, atr = len(c), c[-1], df["atr"].iloc[-1]
    hi, lo = _pivots(c, 4)
    tol = max(0.6 * atr, 0.003 * price)
    a, v = [], 0

    if len(hi) >= 2:
        i1, i2 = hi[-2], hi[-1]
        if abs(c[i1] - c[i2]) <= tol and i2 - i1 >= 8 and n - 1 - i2 <= 25:
            valley = c[i1:i2 + 1].min()
            if price < valley:
                a.append(("bad", "dtop", f"دابل‌تاپ تأیید شد (شکست {valley:,.1f})"))
                v -= 1
            elif price < c[i2]:
                a.append(("warn", "dtop_f", f"دابل‌تاپ در حال شکل‌گیری؛ تأیید با شکست {valley:,.1f}"))
    if len(lo) >= 2:
        i1, i2 = lo[-2], lo[-1]
        if abs(c[i1] - c[i2]) <= tol and i2 - i1 >= 8 and n - 1 - i2 <= 25:
            peak = c[i1:i2 + 1].max()
            if price > peak:
                a.append(("good", "dbot", f"دابل‌باتم تأیید شد (شکست {peak:,.1f})"))
                v += 1
            elif price > c[i2]:
                a.append(("warn", "dbot_f", f"دابل‌باتم در حال شکل‌گیری؛ تأیید با شکست {peak:,.1f}"))
    if len(hi) >= 3:
        p1, p2, p3 = hi[-3:]
        if c[p2] > c[p1] + 0.5 * atr and c[p2] > c[p3] + 0.5 * atr and abs(c[p1] - c[p3]) <= 1.2 * atr and n - 1 - p3 <= 25:
            neck = (c[p1:p2 + 1].min() + c[p2:p3 + 1].min()) / 2
            if price < neck:
                a.append(("bad", "hs", f"سر و شانه تأیید شد (گردنی ≈ {neck:,.1f})"))
                v -= 1
            elif n - 1 - p3 <= 10:
                a.append(("warn", "hs_f", f"سر و شانه در حال شکل‌گیری؛ گردنی ≈ {neck:,.1f}"))
    if len(lo) >= 3:
        p1, p2, p3 = lo[-3:]
        if c[p2] < c[p1] - 0.5 * atr and c[p2] < c[p3] - 0.5 * atr and abs(c[p1] - c[p3]) <= 1.2 * atr and n - 1 - p3 <= 25:
            neck = (c[p1:p2 + 1].max() + c[p2:p3 + 1].max()) / 2
            if price > neck:
                a.append(("good", "ihs", f"سر و شانه‌ی معکوس تأیید شد (گردنی ≈ {neck:,.1f})"))
                v += 1
            elif n - 1 - p3 <= 10:
                a.append(("warn", "ihs_f", f"سر و شانه‌ی معکوس در حال شکل‌گیری؛ گردنی ≈ {neck:,.1f}"))
    return v, a


# ------------------------------------------------------------- فیبوناچی
def fib(df):
    sub = df.iloc[-150:]
    if len(sub) < 60:
        return None, []
    h, l = sub["High"].values, sub["Low"].values
    hi, _ = _pivots(h, 5)
    _, lo = _pivots(l, 5)
    if not hi or not lo:
        return 0, []
    ih, il = hi[-1], lo[-1]
    ph, pl = h[ih], l[il]
    price, atr = sub["Close"].iloc[-1], df["atr"].iloc[-1]
    if abs(ph - pl) < 3 * atr:
        return 0, []
    up = il < ih
    rng = ph - pl
    ret = (ph - price) / rng if up else (price - pl) / rng
    level = (lambda r: ph - r * rng) if up else (lambda r: pl + r * rng)
    a, v = [], 0
    for r in (0.382, 0.5, 0.618, 0.786):
        if abs(price - level(r)) < 0.3 * atr:
            if up:
                a.append(("good", f"fib{r}", f"پولبک به فیبو {r} بعد از ساق صعودی ({level(r):,.1f})؛ ناحیه‌ی بالقوه‌ی خرید" + ("، طلایی‌ترین ناحیه" if r == 0.618 else "")))
            else:
                a.append(("bad", f"fib{r}", f"ریباند به فیبو {r} بعد از ساق نزولی ({level(r):,.1f})؛ ناحیه‌ی بالقوه‌ی فروش" + ("، طلایی‌ترین ناحیه" if r == 0.618 else "")))
            break
    if up:
        if ret > 1:
            a.append(("bad", "fib_break", f"کف ساق صعودی ({pl:,.1f}) شکسته شد؛ ساختار صعودی نقض شد"))
            v = -1
        elif ret < 0:
            ext = lambda r: pl + r * rng
            a.append(("good", "fib_ext", f"عبور از سقف ساق؛ اهداف فیبو 1.272={ext(1.272):,.1f} و 1.618={ext(1.618):,.1f}"))
            v = 1
        elif ret < 0.618:
            v = 1
    else:
        if ret > 1:
            a.append(("good", "fib_break", f"سقف ساق نزولی ({ph:,.1f}) شکسته شد؛ ساختار نزولی نقض شد"))
            v = 1
        elif ret < 0:
            ext = lambda r: ph - r * rng
            a.append(("bad", "fib_ext", f"عبور از کف ساق؛ اهداف فیبو 1.272={ext(1.272):,.1f} و 1.618={ext(1.618):,.1f}"))
            v = -1
        elif ret < 0.618:
            v = -1
    return v, a


# --------------------------------------------------------- ویکوف و حجم
def wyckoff(df):
    n = 40
    if len(df) < 2 * n + 5:
        return None, []
    rng = df.iloc[-n - 1:-1]
    top, bot = rng["High"].max(), rng["Low"].min()
    atr = df["atr"].iloc[-1]
    width = (top - bot) / atr
    L = df.iloc[-1]
    avgv = df["Volume"].tail(20).mean()
    hasv = avgv > 0
    prior = df["Close"].iloc[-n - 1] / df["Close"].iloc[-2 * n - 1] - 1
    ranging = width < 8
    a, v = [], 0
    if ranging:
        ctx = "تراکم" if prior < -0.02 else "توزیع" if prior > 0.02 else "رنج خنثی"
        a.append(("info", "range", f"بازار در رنج فشرده {bot:,.1f}–{top:,.1f} ({ctx} احتمالی بر اساس روند قبلی)"))
        if L["Low"] < bot and L["Close"] > bot:
            a.append(("good", "spring", "اسپرینگ ویکوف: شکست کاذب کف رنج و بازگشت" + (" با حجم بالا (معتبرتر)" if hasv and L["Volume"] > 1.3 * avgv else "")))
            v = 1
        if L["High"] > top and L["Close"] < top:
            a.append(("bad", "upthrust", "آپتراست ویکوف: شکست کاذب سقف رنج و بازگشت" + (" با حجم بالا (معتبرتر)" if hasv and L["Volume"] > 1.3 * avgv else "")))
            v = -1
    if L["Close"] > top:
        a.append(("good", "sos", f"خروج از رنج به بالا ({top:,.1f}): علامت قدرت"))
        v = 1
    elif L["Close"] < bot:
        a.append(("bad", "sow", f"خروج از رنج به پایین ({bot:,.1f}): علامت ضعف"))
        v = -1
    if hasv:
        if L["Volume"] > 2 * avgv and abs(L["Close"] - L["Open"]) < 0.3 * atr:
            a.append(("warn", "effort", "تلاش بدون نتیجه: حجم بسیار بالا ولی حرکت قیمت کم (جذب یا توزیع نهادی)"))
        if L["Volume"] > 2.5 * avgv and (L["High"] - L["Low"]) > 2 * atr:
            a.append(("warn", "climax", "کندل با حجم و دامنه‌ی انفجاری (کلایمکس)؛ بعد از روند طولانی نشانه‌ی احتمالی خستگی"))
    return v, a


# ------------------------------------------------------------- سوپرترند
def supertrend(df, m=3.0):
    if len(df) < 40:
        return None, []
    h, l, c = df["High"].values, df["Low"].values, df["Close"].values
    atr = df["atr"].values
    hl2 = (h + l) / 2
    ub, lb = hl2 + m * atr, hl2 - m * atr
    fub, flb = ub.copy(), lb.copy()
    trend = np.ones(len(c))
    for i in range(1, len(c)):
        fub[i] = ub[i] if (ub[i] < fub[i - 1] or c[i - 1] > fub[i - 1]) else fub[i - 1]
        flb[i] = lb[i] if (lb[i] > flb[i - 1] or c[i - 1] < flb[i - 1]) else flb[i - 1]
        if trend[i - 1] == 1:
            trend[i] = -1 if c[i] < flb[i] else 1
        else:
            trend[i] = 1 if c[i] > fub[i] else -1
    a = []
    line = flb[-1] if trend[-1] == 1 else fub[-1]
    if trend[-1] != trend[-3]:
        a.append(("good" if trend[-1] == 1 else "bad", "flip", "سوپرترند به " + ("صعودی" if trend[-1] == 1 else "نزولی") + " برگشت"))
    a.append(("info", "line", f"خط سوپرترند در {line:,.1f} (حد ضرر دنباله‌دار مرجع)"))
    return int(trend[-1]), a


# ---------------------------------------------------------------- ADX/DMI
def adx(df, n=14):
    if len(df) < 60:
        return None, []
    h, l = df["High"], df["Low"]
    up, dn = h.diff(), -l.diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    mdm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    atr = df["atr"]
    pdi = 100 * pdm.ewm(alpha=1 / n, adjust=False).mean() / atr
    mdi = 100 * mdm.ewm(alpha=1 / n, adjust=False).mean() / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    ax = dx.ewm(alpha=1 / n, adjust=False).mean()
    x = ax.iloc[-1]
    if np.isnan(x):
        return None, []
    a = []
    if x < 18:
        a.append(("warn", "weak", f"ADX={x:.0f}: بازار بدون روند؛ سیگنال‌های روندی کم‌اعتبار و رنج‌زنی محتمل"))
    elif x > 30:
        a.append(("info", "strong", f"ADX={x:.0f}: روند قوی؛ جهت غالب با {'خریداران' if pdi.iloc[-1] > mdi.iloc[-1] else 'فروشندگان'}"))
    if ax.iloc[-4] > 35 and x < ax.iloc[-4]:
        a.append(("warn", "fade", "ADX از سطح بالا در حال افت است؛ روند خسته می‌شود"))
    vote = _sign(pdi.iloc[-1] - mdi.iloc[-1]) if x > 20 else 0
    return vote, a


# -------------------------------------------------------------- استوکاستیک
def stoch(df):
    if len(df) < 40:
        return None, []
    h, l, c = df["High"], df["Low"], df["Close"]
    ll, hh = l.rolling(14).min(), h.rolling(14).max()
    k = (100 * (c - ll) / (hh - ll)).rolling(3).mean()
    d = k.rolling(3).mean()
    kk, dd, pk, pd_ = k.iloc[-1], d.iloc[-1], k.iloc[-2], d.iloc[-2]
    a = []
    if pk <= pd_ and kk > dd and kk < 30:
        a.append(("good", "x_up", f"کراس صعودی استوکاستیک در ناحیه‌ی اشباع فروش ({kk:.0f})"))
    if pk >= pd_ and kk < dd and kk > 70:
        a.append(("bad", "x_dn", f"کراس نزولی استوکاستیک در ناحیه‌ی اشباع خرید ({kk:.0f})"))
    vote = 1 if (kk > dd and kk < 80) else -1 if (kk < dd and kk > 20) else 0
    return vote, a


# --------------------------------------------------------------- پیوت پوینت
def pivot_points(df):
    if len(df) < 5:
        return None, []
    p = df.iloc[-2]
    P = (p["High"] + p["Low"] + p["Close"]) / 3
    r1, s1 = 2 * P - p["Low"], 2 * P - p["High"]
    r2, s2 = P + (p["High"] - p["Low"]), P - (p["High"] - p["Low"])
    price, atr = df["Close"].iloc[-1], df["atr"].iloc[-1]
    a = []
    for name, lv in (("R2", r2), ("R1", r1), ("P", P), ("S1", s1), ("S2", s2)):
        if abs(price - lv) < 0.3 * atr:
            a.append(("info", f"near_{name}", f"قیمت نزدیک پیوت {name} ({lv:,.1f})"))
            break
    return (1 if price > P else -1), a


# ------------------------------------------------------------ هایکن‌آشی
def heikin(df):
    if len(df) < 30:
        return None, []
    o, h, l, c = (df[x].values for x in ("Open", "High", "Low", "Close"))
    atr = df["atr"].iloc[-1]
    hc = (o + h + l + c) / 4
    ho = np.empty(len(c))
    ho[0] = (o[0] + c[0]) / 2
    for i in range(1, len(c)):
        ho[i] = (ho[i - 1] + hc[i - 1]) / 2
    hh, hl = np.maximum(h, np.maximum(ho, hc)), np.minimum(l, np.minimum(ho, hc))
    green = hc > ho
    a = []
    streak = 1
    for i in range(len(c) - 2, 0, -1):
        if green[i] == green[-2]:
            streak += 1
        else:
            break
    if green[-1] != green[-2] and streak >= 3:
        a.append(("warn", "flip", f"تغییر رنگ هایکن‌آشی بعد از {streak} کندل هم‌رنگ؛ احتمال تغییر یا وقفه‌ی روند"))
    if green[-1] and green[-2] and (ho[-1] - hl[-1]) < 0.05 * atr:
        a.append(("good", "nowick", "کندل هایکن‌آشی صعودی بدون سایه‌ی پایین: مومنتوم صعودی قوی"))
    if (not green[-1]) and (not green[-2]) and (hh[-1] - ho[-1]) < 0.05 * atr:
        a.append(("bad", "nowick", "کندل هایکن‌آشی نزولی بدون سایه‌ی بالا: مومنتوم نزولی قوی"))
    vote = 1 if (green[-1] and green[-2]) else -1 if ((not green[-1]) and (not green[-2])) else 0
    return vote, a


# ---------------------------------------------------------------- VWAP و OBV
def vwap_obv(df):
    if df["Volume"].tail(50).mean() <= 0:
        return None, []
    h, l, c, v = df["High"], df["Low"], df["Close"], df["Volume"]
    vwap = ((h + l + c) / 3 * v).rolling(20).sum() / v.rolling(20).sum()
    price, vw = c.iloc[-1], vwap.iloc[-1]
    a = []
    if c.iloc[-2] <= vwap.iloc[-2] and price > vw:
        a.append(("good", "vwap_up", "عبور صعودی از VWAP بیست‌کندلی"))
    elif c.iloc[-2] >= vwap.iloc[-2] and price < vw:
        a.append(("bad", "vwap_dn", "عبور نزولی از VWAP بیست‌کندلی"))
    obv = (np.sign(c.diff().fillna(0)) * v).cumsum()
    w = 20
    if price >= c.tail(w).max() and obv.iloc[-1] < obv.tail(w).max():
        a.append(("warn", "obv_bear", "قیمت سقف ۲۰ کندله زد ولی OBV تأیید نکرد (ضعف مشارکت)"))
    if price <= c.tail(w).min() and obv.iloc[-1] > obv.tail(w).min():
        a.append(("warn", "obv_bull", "قیمت کف ۲۰ کندله زد ولی OBV تأیید نکرد (فشار فروش ضعیف شده)"))
    return _sign(price - vw), a


STYLES = [
    ("ایچیموکو", ichimoku),
    ("اسمارت‌مانی", smc),
    ("پرایس‌اکشن", patterns),
    ("فیبوناچی", fib),
    ("ویکوف/حجم", wyckoff),
    ("سوپرترند", supertrend),
    ("ADX", adx),
    ("استوکاستیک", stoch),
    ("پیوت‌پوینت", pivot_points),
    ("هایکن‌آشی", heikin),
    ("VWAP/OBV", vwap_obv),
]


def run_styles(df):
    votes, alerts = {}, []
    for name, fn in STYLES:
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
