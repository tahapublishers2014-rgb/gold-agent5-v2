# -*- coding: utf-8 -*-
"""لایه‌ی حرفه‌ای: زمان‌بندی سشن‌ها، رژیم بازار، برنامه‌ی معامله و مدیریت ریسک،
سطوح روانی و قبلی، رنج آسیا و روابط بین‌بازاری. فقط طلای جهانی."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

TREND = {"ایچیموکو", "سوپرترند", "ADX", "پارابولیک SAR", "هایکن‌آشی", "اسمارت‌مانی"}
MEANREV = {"استوکاستیک", "فیبوناچی", "ویکوف/حجم", "VWAP/OBV", "پیوت‌پوینت"}
OZ_PER_LOT = 100  # هر لات استاندارد طلا = ۱۰۰ اونس


# ------------------------------------------------------------- سشن‌ها و زمان
def _nth_sunday(year, month, n):
    d = datetime(year, month, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def us_dst(d):
    """آیا آمریکا ساعت تابستانی دارد؟ (یکشنبه‌ی دوم مارس تا یکشنبه‌ی اول نوامبر)"""
    start, end = _nth_sunday(d.year, 3, 2), _nth_sunday(d.year, 11, 1)
    return start <= datetime(d.year, d.month, d.day) < end


def session_alerts(now_utc=None):
    """ساعت‌ها بر پایه‌ی ساعت تابستانی نیویورک (UTC-4)؛ در ساعت زمستانی یک ساعت جلو می‌افتند."""
    now = now_utc or datetime.now(timezone.utc)
    sh = 0 if us_dst(now) else 1
    h = now.hour + now.minute / 60
    wd = now.weekday()  # دوشنبه=۰
    out = []
    # بازار طلا از جمعه ۲۱ تا یکشنبه ۲۲ UTC (زمستانی ۲۲ تا ۲۳) بسته است
    close_h, open_h = 21 + sh, 22 + sh
    if wd == 5 or (wd == 4 and h >= close_h) or (wd == 6 and h < open_h):
        return [("info", "sess_closed", "بازار جهانی طلا بسته است (آخر هفته)؛ قیمت‌ها قدیمی‌اند و با بازگشایی ممکن است شکاف قیمتی ببینی")]
    t = lambda a, b: (a + sh) <= h < (b + sh)
    if t(12, 15.5):
        out.append(("good", "sess_prime", "پنجره‌ی طلایی: هم‌پوشانی لندن و نیویورک؛ عمیق‌ترین نقدینگی و تمیزترین حرکت‌های جهت‌دار"))
    elif t(7, 12):
        out.append(("info", "sess_london", "سشن لندن؛ حجم واقعی از بازگشایی لندن شروع می‌شود و اغلب یک سمت رنج آسیا را می‌شکند"))
    elif t(15.5, 21):
        out.append(("warn", "sess_late", "نیویورک دیروقت: نقدینگی کم، اسپرد بازتر و ادامه‌ی حرکت ضعیف‌تر؛ ورود تازه شانس کمتری دارد"))
    elif t(21, 23):
        out.append(("warn", "sess_roll", "نزدیک رول‌اور (حدود ساعت ۲۱ UTC): اسپرد معمولاً برای لحظاتی بازتر می‌شود و سواپ حساب می‌شود"))
    else:
        out.append(("warn", "sess_asia", "سشن آسیا: حجم کم و رنج فشرده؛ شکست رنج آسیا اغلب جمع‌آوری نقدینگی است، نه حرکت واقعی"))
    # ۳۰ دقیقه قبل از اسلات داده‌های آمریکا (۸:۳۰ به وقت نیویورک)
    data_h = 12.5 + sh
    if wd < 5 and 0 <= data_h - h <= 0.5:
        out.append(("bad", "pre_data", "کمتر از ۳۰ دقیقه به اسلات انتشار داده‌های آمریکا (۸:۳۰ نیویورک): ورود تازه پرخطر است و اسپرد ممکن است چند دلار شود"))
    return out


# ------------------------------------------------------------------ رژیم بازار
def _atr(df, n=14):
    pc = df["Close"].shift()
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - pc).abs(), (df["Low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def regime(df):
    """نسبت کارایی کافمن (۲۰ کندل) و صدک نوسان؛ روند، رنج یا مختلط + نوسان بالا/پایین."""
    c = df["Close"]
    if len(c) < 60:
        return dict(kind="unknown", er=None, atr_pct=None, vol="normal")
    er = abs(c.iloc[-1] - c.iloc[-21]) / max(c.diff().abs().tail(20).sum(), 1e-9)
    atr = _atr(df)
    pct = float((atr.tail(250) <= atr.iloc[-1]).mean())
    kind = "trend" if er > 0.35 else "range" if er < 0.18 else "mixed"
    vol = "high" if pct > 0.9 else "low" if pct < 0.1 else "normal"
    return dict(kind=kind, er=float(er), atr_pct=pct, vol=vol)


def weighted_consensus(votes, kind):
    """در روند، سبک‌های روندی وزن بیشتر؛ در رنج، سبک‌های برگشتی وزن بیشتر."""
    num = den = 0.0
    for name, v in votes.items():
        w = 1.0
        if kind == "trend":
            w = 1.5 if name in TREND else 0.6 if name in MEANREV else 1.0
        elif kind == "range":
            w = 1.5 if name in MEANREV else 0.6 if name in TREND else 1.0
        num += w * v
        den += w
    return 100 * num / den if den else 0.0


def adjusted_score(rep, kind):
    return int(round(0.5 * rep["classic"] + 0.5 * weighted_consensus(rep["votes"], kind)))


# ---------------------------------------------------------------- سطوح قیمتی
def psych_alerts(price, atr):
    out = []
    for step, label in ((100, "عدد رند بزرگ"), (50, "عدد رند")):
        lv = round(price / step) * step
        if abs(price - lv) < 0.4 * atr:
            out.append(("warn", f"psych{step}", f"قیمت نزدیک {label} {lv:,.0f}؛ سطح روانی با سفارش‌های انبوه، جای واکنش یا شکار استاپ"))
            break
    return out


def prior_level_alerts(df_daily):
    out = []
    if len(df_daily) < 10:
        return out
    atr = float(_atr(df_daily).iloc[-1])
    price = df_daily["Close"].iloc[-1]
    ph, pl = df_daily["High"].iloc[-2], df_daily["Low"].iloc[-2]
    lh, ll = df_daily["High"].iloc[-1], df_daily["Low"].iloc[-1]
    if lh > ph and price < ph:
        out.append(("bad", "pdh_sweep", f"جمع‌آوری نقدینگی بالای سقف دیروز ({ph:,.1f}) و بازگشت زیر آن؛ شکست فریب احتمالی"))
    elif ll < pl and price > pl:
        out.append(("good", "pdl_sweep", f"جمع‌آوری نقدینگی زیر کف دیروز ({pl:,.1f}) و بازگشت بالای آن؛ شکست فریب احتمالی"))
    elif abs(price - ph) < 0.3 * atr:
        out.append(("info", "near_pdh", f"قیمت نزدیک سقف دیروز ({ph:,.1f})"))
    elif abs(price - pl) < 0.3 * atr:
        out.append(("info", "near_pdl", f"قیمت نزدیک کف دیروز ({pl:,.1f})"))
    wk = df_daily.tail(6).iloc[:-1]
    if len(wk) >= 4 and price > wk["High"].max():
        out.append(("good", "wk_high", f"بالاتر از سقف ۵ روز گذشته ({wk['High'].max():,.1f})"))
    elif len(wk) >= 4 and price < wk["Low"].min():
        out.append(("bad", "wk_low", f"پایین‌تر از کف ۵ روز گذشته ({wk['Low'].min():,.1f})"))
    return out


def asian_range_alerts(df_1h, now_utc=None):
    """رنج آسیا (۲۳ تا ۰۷ UTC) و شکست فریب آن در سشن لندن."""
    if df_1h is None or len(df_1h) < 30:
        return []
    d = df_1h.copy()
    if d.index.tz is not None:
        d.index = d.index.tz_convert("UTC").tz_localize(None)
    last = d.index[-1]
    day = last.normalize()
    start = day - timedelta(hours=1)  # ۲۳ روز قبل
    end = day + timedelta(hours=7)
    if last < end:  # هنوز در سشن آسیا
        return []
    asia = d[(d.index >= start) & (d.index < end)]
    if len(asia) < 4:
        return []
    ah, al = asia["High"].max(), asia["Low"].min()
    after = d[d.index >= end]
    if after.empty:
        return []
    price = after["Close"].iloc[-1]
    out = [("info", "asia_rng", f"رنج آسیا امروز: {al:,.1f} تا {ah:,.1f}")]
    if after["High"].max() > ah and price < ah:
        out.append(("bad", "asia_sweep_hi", f"قیمت بالای سقف آسیا ({ah:,.1f}) رفت و برگشت؛ جمع‌آوری نقدینگی و شکست فریب احتمالی"))
    elif after["Low"].min() < al and price > al:
        out.append(("good", "asia_sweep_lo", f"قیمت زیر کف آسیا ({al:,.1f}) رفت و برگشت؛ جمع‌آوری نقدینگی و شکست فریب احتمالی"))
    return out


# ------------------------------------------------------- روابط بین‌بازاری
def intermarket_alerts(gold_df, fetch):
    """نسبت طلا به نقره و قدرت نسبی طلا در برابر دلار؛ هر خطا بی‌صدا رد می‌شود."""
    out = []
    g = gold_df["Close"]
    try:
        si = fetch("SI=F", "1d")["Close"]
        j = pd.concat([g, si], axis=1, join="inner").dropna().tail(250)
        j.columns = ["g", "s"]
        ratio = j["g"] / j["s"]
        z = (ratio.iloc[-1] - ratio.mean()) / ratio.std()
        if z > 2:
            out.append(("info", "gsr_hi", f"نسبت طلا به نقره {ratio.iloc[-1]:.0f} (بالاتر از میانگین سالانه، z={z:.1f}): نشانه‌ی ترس بازار؛ گاهی نقره عقب‌مانده را جبران می‌کند"))
        elif z < -2:
            out.append(("info", "gsr_lo", f"نسبت طلا به نقره {ratio.iloc[-1]:.0f} (پایین‌تر از میانگین سالانه، z={z:.1f}): نقره قوی‌تر از طلا؛ رغبت به ریسک"))
    except Exception:
        pass
    try:
        dxy = fetch("DX-Y.NYB", "1d")["Close"]
        j = pd.concat([g, dxy], axis=1, join="inner").dropna().tail(80)
        j.columns = ["g", "d"]
        cg, cd = j["g"].iloc[-1] / j["g"].iloc[-21] - 1, j["d"].iloc[-1] / j["d"].iloc[-21] - 1
        if cg > 0.02 and cd > 0.01:
            out.append(("good", "rel_str", f"طلا با وجود قوی‌شدن دلار ({cd:+.1%}) بالا رفته ({cg:+.1%}): قدرت ذاتی؛ معمولاً خرید بانک‌های مرکزی یا ژئوپلیتیک پشتش است"))
        elif cg < -0.02 and cd < -0.01:
            out.append(("bad", "rel_weak", f"طلا با وجود ضعیف‌شدن دلار ({cd:+.1%}) پایین رفته ({cg:+.1%}): ضعف ذاتی؛ حمایت همیشگی دلار کار نمی‌کند"))
        corr = j[["g", "d"]].pct_change().dropna().corr().iloc[0, 1]
        if corr > 0.1:
            out.append(("info", "corr_off", f"همبستگی معکوس همیشگی طلا و دلار از کار افتاده ({corr:+.2f}); محرک دیگری (بانک‌های مرکزی، ژئوپلیتیک) غالب است"))
    except Exception:
        pass
    return out


# ------------------------------------------------------ برنامه‌ی معامله
def trade_plan(rep, adj, reg, news_bias=0, min_adj=25, min_rr=1.5, equity=10000, risk_pct=1.0):
    """نقطه‌ی ورود، حد ضرر، حد سود و حجم بر پایه‌ی ATR و سطوح ساختاری. اگر شرایط خوب نباشد: «معامله نکن»."""
    price, atr = rep["price"], rep["atr"]
    why_not = []
    if abs(adj) < min_adj:
        return dict(side=None, reason=f"امتیاز تعدیل‌شده {adj:+d} به آستانه‌ی ±{min_adj} نرسیده؛ برتری آماری روشن نیست. بهترین معامله گاهی «بی‌معامله» است")
    side = 1 if adj > 0 else -1
    if reg["kind"] == "range" and abs(adj) < 45:
        why_not.append("بازار رنج است و سیگنال به‌اندازه‌ی کافی قوی نیست")
    if news_bias * side <= -25:
        why_not.append(f"اخبار (امتیاز {news_bias:+d}) خلاف جهت است")
    sup, res = rep.get("sup"), rep.get("res")
    if side == 1:
        sl = price - 1.5 * atr
        if sup and sup < price:
            sl = min(sl, sup - 0.25 * atr)
        sl = max(sl, price - 3 * atr)
        target_lvl = res
    else:
        sl = price + 1.5 * atr
        if res and res > price:
            sl = max(sl, res + 0.25 * atr)
        sl = min(sl, price + 3 * atr)
        target_lvl = sup
    risk = abs(price - sl)
    tp1, tp2 = price + side * risk, price + side * 2 * risk
    rr_lvl = None
    if target_lvl and (target_lvl - price) * side > 0:
        rr_lvl = abs(target_lvl - price) / risk
        if rr_lvl < min_rr:
            why_not.append(f"سطح مقابل ({target_lvl:,.1f}) فقط {rr_lvl:.1f}R فاصله دارد؛ نسبت سود به ضرر کم است")
    risk_usd = equity * risk_pct / 100
    lots = risk_usd / (risk * OZ_PER_LOT)
    plan = dict(side="long" if side == 1 else "short", entry=price, sl=sl, tp1=tp1, tp2=tp2, risk=risk,
                rr_level=rr_lvl, lots=lots, equity=equity, risk_pct=risk_pct, risk_usd=risk_usd,
                blockers=why_not)
    if why_not:
        plan["reason"] = "؛ ".join(why_not)
    return plan


# ------------------------------------------------------------ ورودی اصلی
def pro_analysis(reps, dfs, news_bias, fetch, macro=True, now_utc=None):
    """reps/dfs: برای هر تایم‌فریم. خروجی: هشدارهای اضافی و برنامه‌ی معامله روی تایم‌فریم اصلی."""
    extra = []
    primary = next((r for r in reps if r["tf"] == "1d"), reps[0])
    pdf = dfs[primary["tf"]]
    reg = regime(pdf)
    adj = adjusted_score(primary, reg["kind"])
    names = {"trend": "روندی", "range": "رنج", "mixed": "مختلط", "unknown": "نامشخص"}
    txt = f"رژیم بازار ({primary['tf']}): {names[reg['kind']]}"
    if reg["er"] is not None:
        txt += f" (ضریب کارایی {reg['er']:.2f})"
    if reg["kind"] == "trend":
        txt += "؛ وزن سبک‌های روندی بیشتر شد"
    elif reg["kind"] == "range":
        txt += "؛ وزن سبک‌های برگشتی بیشتر شد و شکست‌ها کم‌اعتبارترند"
    extra.append(("info", "regime", txt))
    if reg["vol"] == "high":
        extra.append(("warn", "vol_hi", f"نوسان در صدک {reg['atr_pct']:.0%} سال اخیر؛ حد ضرر را بازتر و حجم را کمتر بگیر"))
    elif reg["vol"] == "low":
        extra.append(("warn", "vol_lo", f"نوسان در صدک {reg['atr_pct']:.0%} سال اخیر (خیلی کم)؛ معمولاً قبل از حرکت بزرگ است"))
    extra += session_alerts(now_utc)
    extra += psych_alerts(primary["price"], primary["atr"])
    daily = dfs.get("1d")
    if daily is not None:
        extra += prior_level_alerts(daily)
    if "1h" in dfs:
        extra += asian_range_alerts(dfs["1h"], now_utc)
    if macro and daily is not None:
        extra += intermarket_alerts(daily, fetch)
    plan = trade_plan(primary, adj, reg, news_bias)
    return dict(extra=extra, plan=plan, regime=reg, adj=adj, tf=primary["tf"])


def plan_lines(pro):
    """متن فارسی برنامه‌ی معامله."""
    p = pro["plan"]
    if p.get("side") is None:
        return [f"برنامه‌ی معامله: معامله نکن. {p['reason']}"]
    side = "خرید (Long)" if p["side"] == "long" else "فروش (Short)"
    L = []
    if p["blockers"]:
        L.append("فعلاً وارد نشو: " + p["reason"])
        L.append(f"اگر با این حال وارد شدی، طرح محتاطانه ({side}):")
    else:
        L.append(f"جهت پیشنهادی: {side} · امتیاز تعدیل‌شده {pro['adj']:+d}")
    L += [f"ورود نزدیک {p['entry']:,.1f} · حد ضرر {p['sl']:,.1f} (ریسک {p['risk']:,.1f} دلار در هر اونس)",
          f"حد سود ۱: {p['tp1']:,.1f} (1R) · حد سود ۲: {p['tp2']:,.1f} (2R)",
          f"حجم برای سرمایه‌ی {p['equity']:,.0f} دلاری با ریسک {p['risk_pct']:g}٪ ({p['risk_usd']:,.0f} دلار): حدود {p['lots']:.3f} لات "
          f"(هر لات ۱۰۰ اونس؛ ۰٫۰۱ لات = ۱ اونس)"]
    L.append("قواعد: حد ضرر همزمان با ورود، ریسک هر معامله حداکثر ۱ تا ۲٪، سقف ضرر روزانه ۳٪، میانگین‌گیری روی ضرر ممنوع، ۳۰ دقیقه قبل از اخبار مهم ورود نکن.")
    return L
