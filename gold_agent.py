#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gold Agent - ایجنت تحلیل رفتار چارت طلا

فقط بازار جهانی طلا (XAU/USD): نماد GC=F یا XAUUSD=X
نصب:    pip install -r requirements.txt
اختیاری: متغیر محیطی ANTHROPIC_API_KEY برای حدس خبری استدلالی با Claude
گزارش HTML راست‌به‌چپ (برای ویندوز پیشنهاد می‌شود):  python gold_agent.py --html
اجرا:   python gold_agent.py                 (تحلیل یک‌باره)
        python gold_agent.py --watch 900     (هر ۱۵ دقیقه چک کن و فقط هشدار تازه بده)
        python gold_agent.py --demo          (تست با داده‌ی مصنوعی، بدون اینترنت)
        python gold_agent.py --symbol XAUUSD=X --tf 1h,1d,1wk

توجه: این ابزار کمک‌تصمیم است، نه پیش‌بینی قطعی و نه مشاوره‌ی مالی.
"""
import argparse
import csv
import json
import os
import platform
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

import numpy as np
import pandas as pd

import contextlib
import html
import io
import re
import webbrowser

from gold_styles import run_styles  # باید کنار همین فایل باشد
from gold_styles_extra import run_extra
from gold_news import news_report, news_alerts
from gold_pro import pro_analysis, plan_lines

os.system("")  # فعال‌سازی رنگ ANSI در ویندوز
G, R, Y, C, B, X = "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[1m", "\033[0m"
ICON = {"good": f"{G}🟢 خوب{X}", "bad": f"{R}🔴 بد{X}", "warn": f"{Y}🟡 احتیاط{X}", "info": f"{C}🔵 نکته{X}"}

PERIOD = {"1h": "60d", "1d": "2y", "1wk": "10y"}
TF_FA = {"1h": "ساعتی", "1d": "روزانه", "1wk": "هفتگی"}


# ----------------------------------------------------------------- داده
def _parse_chart(js):
    r = js["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    idx = pd.to_datetime(r["timestamp"], unit="s")
    df = pd.DataFrame({"Open": q["open"], "High": q["high"], "Low": q["low"],
                       "Close": q["close"], "Volume": q.get("volume") or [0] * len(idx)}, index=idx)
    df["Volume"] = df["Volume"].fillna(0)
    return df.dropna(subset=["Close", "Open", "High", "Low"])


def fetch_direct(symbol, interval):
    """بدون yfinance: مستقیم از API چارت یاهو (برای Termux و جاهایی که yfinance نصب نمی‌شود)."""
    rng = PERIOD.get(interval, "2y")
    last = None
    for host in ("query1", "query2"):
        url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
               f"?range={rng}&interval={interval}&includePrePost=false")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return _parse_chart(json.loads(r.read().decode()))
        except Exception as e:
            last = e
    raise RuntimeError(f"دریافت قیمت از یاهو ناموفق بود ({last}); اینترنت یا VPN را بررسی کن")


def fetch(symbol, interval):
    try:
        import yfinance as yf
        df = yf.download(symbol, period=PERIOD.get(interval, "2y"), interval=interval,
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df = df.rename(columns=str.title).dropna(subset=["Close"])
        if len(df) < 60:
            raise RuntimeError("short")
    except Exception:
        df = fetch_direct(symbol, interval)
    if len(df) < 60:
        raise RuntimeError(f"داده‌ی کافی برای {symbol} / {interval} نیامد")
    return df


def synthetic(n=600, seed=7):
    rng = np.random.default_rng(seed)
    ret = rng.normal(0.0004, 0.009, n)
    ret[-8:] += 0.004  # یک حرکت صعودی در انتها
    close = 1900 * np.exp(np.cumsum(ret))
    open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.004, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.004, n))
    vol = rng.integers(80_000, 200_000, n).astype(float)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol}, index=idx)


# ------------------------------------------------------------ اندیکاتورها
def add_indicators(df):
    c, h, l = df["Close"], df["High"], df["Low"]
    df["sma20"], df["sma50"], df["sma200"] = (c.rolling(n).mean() for n in (20, 50, 200))
    df["ema20"] = c.ewm(span=20, adjust=False).mean()

    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    df["rsi"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))

    ema12, ema26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_sig"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_sig"]

    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()

    sd = c.rolling(20).std()
    df["bb_up"], df["bb_lo"] = df["sma20"] + 2 * sd, df["sma20"] - 2 * sd
    df["bb_w"] = (df["bb_up"] - df["bb_lo"]) / df["sma20"]
    df["pctb"] = (c - df["bb_lo"]) / (df["bb_up"] - df["bb_lo"])
    df["hh20"], df["ll20"] = h.rolling(20).max().shift(), l.rolling(20).min().shift()
    return df


def pivots(s, w=3):
    """اندیس قله‌ها و کف‌های محلی."""
    v = s.values
    hi, lo = [], []
    for i in range(w, len(v) - w):
        win = v[i - w:i + w + 1]
        if v[i] == win.max():
            hi.append(i)
        if v[i] == win.min():
            lo.append(i)
    return hi, lo


def nearest_levels(df, lookback=150):
    sub = df.iloc[-lookback:]
    hi, lo = pivots(sub["Close"], 4)
    price = sub["Close"].iloc[-1]
    res = sorted(p for p in (sub["Close"].iloc[i] for i in hi) if p > price)
    sup = sorted((p for p in (sub["Close"].iloc[i] for i in lo) if p < price), reverse=True)
    return (sup[0] if sup else None), (res[0] if res else None)


# --------------------------------------------------------------- تحلیل
def analyze(df, tf):
    df = add_indicators(df.copy())
    a = []  # (level, key, text)
    L, P = df.iloc[-1], df.iloc[-2]
    price, atr = L["Close"], L["atr"]
    has_vol = df["Volume"].tail(50).mean() > 0

    # ---- امتیاز روند و مومنتوم
    s = 0
    if not np.isnan(L["sma50"]):
        s += 20 if price > L["sma50"] else -20
    if not np.isnan(L["sma200"]) and not np.isnan(L["sma50"]):
        s += 15 if L["sma50"] > L["sma200"] else -15
    s += 10 if L["ema20"] > df["ema20"].iloc[-6] else -10
    s += 10 if L["macd_hist"] > 0 else -10
    s += 5 if L["macd_hist"] > P["macd_hist"] else -5
    r = L["rsi"]
    s += 10 if 50 <= r <= 70 else -10 if 30 <= r < 50 else -5 if r > 70 else 5
    if L["pctb"] > 1:
        s -= 5
    elif L["pctb"] < 0:
        s += 5
    score = int(max(-100, min(100, s * 1.4)))

    # ---- RSI
    if r >= 75:
        a.append(("bad", "rsi_ob", f"RSI={r:.0f}: اشباع خرید شدید، احتمال اصلاح بالاست"))
    elif r >= 70:
        a.append(("warn", "rsi_ob", f"RSI={r:.0f}: ورود به اشباع خرید، دنبال کردن صعود ریسک دارد"))
    elif r <= 25:
        a.append(("good", "rsi_os", f"RSI={r:.0f}: اشباع فروش شدید، احتمال برگشت یا پولبک"))
    elif r <= 30:
        a.append(("warn", "rsi_os", f"RSI={r:.0f}: اشباع فروش؛ منتظر تأیید برگشت بمان"))

    # ---- مکدی
    if P["macd"] <= P["macd_sig"] and L["macd"] > L["macd_sig"]:
        a.append(("good", "macd_x", "کراس صعودی مکدی" + (" زیر صفر (ضعیف‌تر)" if L["macd"] < 0 else " بالای صفر (قوی‌تر)")))
    elif P["macd"] >= P["macd_sig"] and L["macd"] < L["macd_sig"]:
        a.append(("bad", "macd_x", "کراس نزولی مکدی" + (" زیر صفر (قوی‌تر)" if L["macd"] < 0 else " بالای صفر (هشدار ضعف)")))

    # ---- گلدن/دث کراس
    cross = (df["sma50"] > df["sma200"]).astype(int).diff().tail(3)
    if (cross == 1).any():
        a.append(("good", "golden", "گلدن‌کراس: SMA50 به بالای SMA200 رسید"))
    if (cross == -1).any():
        a.append(("bad", "death", "دث‌کراس: SMA50 به زیر SMA200 رفت"))

    # ---- واگرایی RSI
    sub = df.iloc[-60:]
    hi, lo = pivots(sub["Close"], 3)
    n = len(sub)
    if len(hi) >= 2 and n - 1 - hi[-1] <= 10:
        i1, i2 = hi[-2], hi[-1]
        if sub["Close"].iloc[i2] > sub["Close"].iloc[i1] and sub["rsi"].iloc[i2] < sub["rsi"].iloc[i1] - 2:
            a.append(("bad", "div_bear", "واگرایی منفی: قیمت سقف بالاتر زده ولی RSI ضعیف‌تر شده؛ صعود جان کم می‌آورد"))
    if len(lo) >= 2 and n - 1 - lo[-1] <= 10:
        i1, i2 = lo[-2], lo[-1]
        if sub["Close"].iloc[i2] < sub["Close"].iloc[i1] and sub["rsi"].iloc[i2] > sub["rsi"].iloc[i1] + 2:
            a.append(("good", "div_bull", "واگرایی مثبت: قیمت کف پایین‌تر زده ولی RSI قوی‌تر شده؛ فشار فروش تحلیل می‌رود"))

    # ---- فشردگی بولینگر (آرامش قبل از طوفان)
    w = df["bb_w"].dropna().tail(120)
    if len(w) > 60 and L["bb_w"] <= w.quantile(0.10):
        a.append(("warn", "squeeze", "فشردگی شدید بولینگر: نوسان کم شده و معمولاً شکست بزرگ نزدیک است (جهتش هنوز معلوم نیست)"))

    # ---- شکست سقف/کف ۲۰ کندلی
    vol_ok = has_vol and L["Volume"] > 1.3 * df["Volume"].tail(20).mean()
    if price > L["hh20"]:
        a.append(("good", "brk_up", "شکست سقف ۲۰ کندل اخیر" + (" با حجم بالا (معتبرتر)" if vol_ok else " بدون تأیید حجم (احتمال شکست فریب)")))
    elif price < L["ll20"]:
        a.append(("bad", "brk_dn", "شکست کف ۲۰ کندل اخیر" + (" با حجم بالا (معتبرتر)" if vol_ok else " بدون تأیید حجم (احتمال شکست فریب)")))

    # ---- الگوهای کندلی
    o, c_, h, l = L["Open"], L["Close"], L["High"], L["Low"]
    body, rng = abs(c_ - o), h - l
    upper, lower = h - max(o, c_), min(o, c_) - l
    if rng > 0:
        if body > 0 and lower >= 2 * body and upper <= 0.5 * body and price < L["sma20"]:
            a.append(("good", "hammer", "کندل چکش در ناحیه ریزشی: نشانه‌ی جذب فشار فروش"))
        if body > 0 and upper >= 2 * body and lower <= 0.5 * body and price > L["sma20"]:
            a.append(("bad", "star", "کندل ستاره‌ی دنباله‌دار در ناحیه صعودی: رد قیمت‌های بالا"))
        if body <= 0.1 * rng:
            a.append(("info", "doji", "کندل دوجی: بلاتکلیفی بازار؛ کندل بعدی را ببین"))
    if P["Close"] < P["Open"] and c_ > o and o <= P["Close"] and c_ >= P["Open"]:
        a.append(("good", "eng_bull", "الگوی انگالفینگ صعودی"))
    if P["Close"] > P["Open"] and c_ < o and o >= P["Close"] and c_ <= P["Open"]:
        a.append(("bad", "eng_bear", "الگوی انگالفینگ نزولی"))

    # ---- نوسان غیرعادی
    mv = abs(c_ - P["Close"])
    if mv > 2 * P["atr"]:
        a.append(("warn", "bigmove", f"حرکت غیرعادی: آخرین کندل {mv / P['atr']:.1f} برابر نوسان معمول (ATR) بود؛ خبر یا نقدینگی‌ی ناگهانی؟"))
    if L["atr"] > 1.5 * df["atr"].tail(60).mean():
        a.append(("warn", "atr_up", "نوسان‌پذیری بالاتر از حد معمول؛ حجم معامله و حد ضرر را با احتیاط تنظیم کن"))

    # ---- فاصله از میانگین (کشش بیش از حد)
    ext = (price - L["sma50"]) / atr if not np.isnan(L["sma50"]) else 0
    if ext > 4:
        a.append(("warn", "stretch_up", f"قیمت {ext:.1f} ATR بالای SMA50 است؛ کشیده شده و پولبک محتمل‌تر است"))
    elif ext < -4:
        a.append(("warn", "stretch_dn", f"قیمت {abs(ext):.1f} ATR زیر SMA50 است؛ کشیده شده و پولبک بالا محتمل‌تر است"))

    # ---- حمایت/مقاومت
    sup, res = nearest_levels(df)
    if res and (res - price) < 0.7 * atr:
        a.append(("warn", "near_res", f"نزدیک مقاومت {res:,.1f}؛ جای واکنش یا شکست"))
    if sup and (price - sup) < 0.7 * atr:
        a.append(("warn", "near_sup", f"نزدیک حمایت {sup:,.1f}؛ جای واکنش یا شکست"))

    # ---- سبک‌های دیگر (SMC، ایچیموکو، فیبو، ویکوف، ...) و رأی‌گیری
    votes, st_alerts = run_styles(df)
    v2, a2 = run_extra(df)  # الیوت، هارمونیک، ولیوم‌پروفایل، پارابولیک SAR
    votes.update(v2)
    st_alerts += a2
    votes = {"کلاسیک": 1 if score >= 15 else -1 if score <= -15 else 0, **votes}
    a += st_alerts
    consensus = int(round(100 * sum(votes.values()) / len(votes)))
    classic_score = score
    score = int(round(0.5 * classic_score + 0.5 * consensus))

    return dict(tf=tf, price=price, score=score, classic=classic_score, votes=votes,
                atr=atr, sup=sup, res=res, rsi=r,
                trend_up=bool(price > L["sma50"]) if not np.isnan(L["sma50"]) else None,
                alerts=a, time=df.index[-1])


def bias_label(score):
    if score >= 40: return f"{G}صعودی قوی{X}"
    if score >= 15: return f"{G}متمایل به صعود{X}"
    if score > -15: return f"{Y}خنثی / بدون جهت مشخص{X}"
    if score > -40: return f"{R}متمایل به نزول{X}"
    return f"{R}نزولی قوی{X}"


# ------------------------------------------------------ عوامل بنیادی ساده
def macro_alerts(gold_df):
    out = []
    try:
        dxy = fetch("DX-Y.NYB", "1d")["Close"]
        g = gold_df["Close"]
        j = pd.concat([g.pct_change(), dxy.pct_change()], axis=1, join="inner").dropna().tail(60)
        corr = j.corr().iloc[0, 1]
        chg = dxy.iloc[-1] / dxy.iloc[-21] - 1
        if chg > 0.015:
            out.append(("bad" if corr < -0.2 else "warn", "dxy_up",
                        f"دلار آمریکا ۲۰ روزه {chg*100:+.1f}٪ قوی‌تر شده (همبستگی اخیر با طلا {corr:+.2f}): باد مخالف طلا"))
        elif chg < -0.015:
            out.append(("good" if corr < -0.2 else "info", "dxy_dn",
                        f"دلار آمریکا ۲۰ روزه {chg*100:+.1f}٪ ضعیف‌تر شده (همبستگی اخیر با طلا {corr:+.2f}): باد موافق طلا"))
        if corr > 0.2:
            out.append(("info", "corr_flip", f"همبستگی طلا و دلار این روزها غیرعادی مثبت است ({corr:+.2f}); احتمالاً عامل دیگری بازار را می‌چرخاند"))
    except Exception:
        pass
    try:
        y = fetch("^TNX", "1d")["Close"]
        chg = y.iloc[-1] - y.iloc[-21]
        if chg > 0.25:
            out.append(("bad", "yld_up", f"بازده اوراق ۱۰ ساله آمریکا ۲۰ روزه {chg:+.2f} واحد بالا رفته؛ فشار روی طلا"))
        elif chg < -0.25:
            out.append(("good", "yld_dn", f"بازده اوراق ۱۰ ساله آمریکا ۲۰ روزه {chg:+.2f} واحد پایین آمده؛ حمایت از طلا"))
    except Exception:
        pass
    return out


# ------------------------------------------------------------- اجرا و گزارش
def run_once(args):
    reps, gold_daily, dfs = [], None, {}
    for tf in args.tf.split(","):
        df = synthetic(seed=hash(tf) % 100) if args.demo else fetch(args.symbol, tf)
        if tf == "1d":
            gold_daily = df
        dfs[tf] = df
        reps.append(analyze(df, tf))

    extra = []
    scores = [r["score"] for r in reps]
    if len(reps) > 1:
        if all(s >= 15 for s in scores):
            extra.append(("good", "mtf_up", "همسویی تایم‌فریم‌ها: همه به سمت صعود"))
        elif all(s <= -15 for s in scores):
            extra.append(("bad", "mtf_dn", "همسویی تایم‌فریم‌ها: همه به سمت نزول"))
        elif max(scores) >= 15 and min(scores) <= -15:
            extra.append(("warn", "mtf_conf", "تضاد تایم‌فریم‌ها: کوتاه‌مدت و بلندمدت هم‌جهت نیستند؛ سیگنال‌ها قابل‌اعتماد کمتری دارند"))
    if not args.demo and not args.no_macro and gold_daily is not None:
        extra += macro_alerts(gold_daily)

    news = None
    if not args.no_news:
        try:
            news = news_report(hours=args.news_hours, use_llm=not args.no_llm, demo=args.demo)
            extra += news_alerts(news)
        except Exception as e:
            extra.append(("warn", "news_fail", f"دریافت اخبار ناموفق بود ({e}); برای اخبار به اینترنت یا VPN نیاز است"))

    try:
        nb0 = news["bias"] if news else 0
        pro = pro_analysis(reps, dfs, nb0, fetch, macro=(not args.demo and not args.no_macro))
        extra += pro["extra"]
        reps[0]["pro"] = pro
    except Exception as e:
        extra.append(("warn", "pro_fail", f"بخش حرفه‌ای (سشن، رژیم، برنامه‌ی معامله) اجرا نشد: {e}"))

    tech = int(np.mean(scores))
    overall = tech
    if news:
        nb = news["bias"]
        overall = int(round(0.75 * tech + 0.25 * nb))
        if (tech >= 15 and nb <= -15) or (tech <= -15 and nb >= 15):
            extra.append(("warn", "tech_news_conflict", f"تضاد خبر و تکنیکال: تکنیکال {tech:+d} ولی اخبار {nb:+d}؛ بازار ممکن است بین دو نیرو نوسان کند، با احتیاط عمل کن"))
        elif tech >= 15 and nb >= 15:
            extra.append(("good", "tech_news_agree", "هم‌راستایی خبر و تکنیکال: هر دو به سمت صعود"))
        elif tech <= -15 and nb <= -15:
            extra.append(("bad", "tech_news_agree", "هم‌راستایی خبر و تکنیکال: هر دو به سمت نزول"))
    reps[0]["_dfs"] = dfs
    return reps, extra, news, overall


def render_news(news):
    mode = "تحلیل Claude" if news["mode"] == "claude" else "قاعده‌ی کلیدواژه‌ای"
    print(f"\n{B}▌حدس بر اساس اخبار روز جهان{X}  ({mode})")
    print(f"   جهت‌گیری خبری: {bias_label(news['bias'])} (امتیاز {news['bias']:+d}) · اطمینان: {news['conf']} · "
          f"{news['n']} خبر بررسی شد، {news['n_imp']} خبر اثرگذار")
    if news.get("note"):
        print(f"   {Y}{news['note']}{X}")
    if news.get("summary"):
        print("   " + news["summary"])
    if not news["top"]:
        print("   خبر اثرگذار روشنی در این بازه پیدا نشد.")
    for x in news["top"]:
        arrow = f"{G}▲{X}" if x["score"] > 0 else f"{R}▼{X}" if x["score"] < 0 else f"{Y}■{X}"
        why = (" → " + x["why"][0]) if x["why"] and x["why"][0] else ""
        print(f"   {arrow} {x['title']} ({x['source']}، {x['age_h']:.0f} ساعت پیش){why}")
    if news.get("risks"):
        print(f"   ابطال حدس: {news['risks']}")
    print(f"   {Y}این حدس فقط از تیتر خبرها ساخته شده و واکنش واقعی بازار ممکن است برعکس باشد.{X}")


def render(reps, extra, news, overall, args):
    print(f"\n{B}══ ایجنت طلا · {args.symbol} · {datetime.now():%Y-%m-%d %H:%M} ══{X}")
    for r in reps:
        print(f"\n{B}▌تایم‌فریم {TF_FA.get(r['tf'], r['tf'])}{X}  قیمت: {r['price']:,.2f}  |  امتیاز: {r['score']:+d}  →  {bias_label(r['score'])}")
        lv = []
        if r["sup"]: lv.append(f"حمایت نزدیک {r['sup']:,.1f}")
        if r["res"]: lv.append(f"مقاومت نزدیک {r['res']:,.1f}")
        lv.append(f"نوسان معمول (ATR) ≈ {r['atr']:,.1f}")
        print("   " + "  |  ".join(lv))
        vs = r["votes"]
        nb, ns = sum(v > 0 for v in vs.values()), sum(v < 0 for v in vs.values())
        arrows = "  ".join(f"{n} {G + '▲' if v > 0 else R + '▼' if v < 0 else Y + '■'}{X}" for n, v in vs.items())
        print(f"   رأی سبک‌ها: {G}{nb} صعودی{X} · {R}{ns} نزولی{X} · {Y}{len(vs) - nb - ns} خنثی{X}")
        print(f"   {arrows}")
        order = {"bad": 0, "good": 1, "warn": 2, "info": 3}
        for lvl, _, txt in sorted(r["alerts"], key=lambda x: order[x[0]]):
            print(f"   {ICON[lvl]}  {txt}")
    if news:
        render_news(news)
    if extra:
        print(f"\n{B}▌جمع‌بندی چندزمانی، اخبار و عوامل بنیادی{X}")
        for lvl, _, txt in extra:
            print(f"   {ICON[lvl]}  {txt}")

    pro = reps[0].get("pro")
    if pro:
        print(f"\n{B}▌برنامه‌ی معامله و مدیریت ریسک{X}")
        for ln in plan_lines(pro):
            print(f"   {ln}")

    avg = overall
    r0 = reps[min(1, len(reps) - 1)]
    print(f"\n{B}▌برداشت کلی{X}: {bias_label(avg)} (میانگین امتیاز {avg:+d})")
    if r0["sup"] and r0["res"]:
        print(f"   سناریوی صعودی با عبور پایدار از {r0['res']:,.1f} تقویت می‌شود؛ سناریوی نزولی با شکست {r0['sup']:,.1f}.")
    print(f"{Y}   هشدار: این خروجی احتمال و سناریو است، نه پیش‌بینی قطعی یا مشاوره‌ی مالی. حد ضرر و مدیریت سرمایه با خودت.{X}\n")


def notify(title, msg):
    try:
        sysname = platform.system()
        if sysname == "Darwin":
            subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "{title}"'], check=False)
        elif sysname == "Linux":
            subprocess.run(["notify-send", title, msg], check=False)
        elif sysname == "Windows":
            import ctypes, threading
            threading.Thread(target=lambda: ctypes.windll.user32.MessageBoxW(0, msg, title, 0x40), daemon=True).start()
    except Exception:
        pass
    print("\a", end="")
    tok, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if tok and chat:
        try:
            data = urllib.parse.urlencode({"chat_id": chat, "text": f"{title}\n{msg}"}).encode()
            urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data, timeout=10)
        except Exception:
            pass


def log_alerts(items):
    new = not os.path.exists("gold_alerts_log.csv")
    with open("gold_alerts_log.csv", "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "timeframe", "level", "text"])
        for tf, lvl, txt in items:
            w.writerow([datetime.now().isoformat(timespec="seconds"), tf, lvl, txt])


ANSI_RE = re.compile(r"\033\[(\d+)m")
HTML_TAGS = {"1": '<span style="font-weight:bold">', "92": '<span style="color:#4ade80">',
             "91": '<span style="color:#f87171">', "93": '<span style="color:#facc15">',
             "96": '<span style="color:#67e8f9">'}
_opened = {"done": False}


def ansi_to_html(text):
    text = html.escape(text).replace("\a", "")
    out, open_n, pos = [], 0, 0
    for m in ANSI_RE.finditer(text):
        out.append(text[pos:m.start()])
        pos = m.end()
        if m.group(1) == "0":
            out.append("</span>" * open_n)
            open_n = 0
        elif m.group(1) in HTML_TAGS:
            out.append(HTML_TAGS[m.group(1)])
            open_n += 1
    out.append(text[pos:])
    out.append("</span>" * open_n)
    return "".join(out)


def write_html(text, refresh):
    meta = f'<meta http-equiv="refresh" content="{max(30, refresh)}">' if refresh else ""
    page = (f'<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">{meta}'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>ایجنت طلا</title>'
            '<style>body{background:#0f1115;color:#e6e6e6;font:15px/1.9 Tahoma,Vazirmatn,sans-serif;margin:0;padding:16px}'
            'pre{white-space:pre-wrap;word-break:break-word;font:inherit;margin:0}</style></head>'
            f'<body><pre>{ansi_to_html(text)}</pre></body></html>')
    path = os.path.abspath("gold_report.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    if not _opened["done"]:
        _opened["done"] = True
        try:
            webbrowser.open("file://" + path)
        except Exception:
            pass
    return path


def main():
    ap = argparse.ArgumentParser(description="ایجنت تحلیل رفتار چارت طلای جهانی")
    ap.add_argument("--symbol", default="GC=F", help="طلای جهانی: GC=F (فیوچرز، پیش‌فرض) یا XAUUSD=X (اسپات)")
    ap.add_argument("--tf", default="1d,1wk", help="تایم‌فریم‌ها: 1h,1d,1wk")
    ap.add_argument("--watch", type=int, default=0, help="ثانیه بین هر بررسی؛ ۰ یعنی یک‌بار")
    ap.add_argument("--no-macro", action="store_true", help="بدون بررسی دلار و بازده اوراق")
    ap.add_argument("--demo", action="store_true", help="داده‌ی مصنوعی برای تست")
    ap.add_argument("--no-news", action="store_true", help="بدون اخبار روز جهان")
    ap.add_argument("--no-llm", action="store_true", help="اخبار فقط با قاعده‌ی کلیدواژه‌ای (بدون Claude)")
    ap.add_argument("--news-hours", type=int, default=24, help="اخبار چند ساعت اخیر را بررسی کن (پیش‌فرض ۲۴)")
    ap.add_argument("--html", action="store_true", help="گزارش راست‌به‌چپ gold_report.html بساز و در مرورگر باز کن")
    args = ap.parse_args()

    seen = {}
    while True:
        try:
            reps, extra, news, overall = run_once(args)
        except Exception as e:
            print(f"{R}خطا در دریافت داده: {e}{X}")
            if not args.watch:
                sys.exit(1)
            time.sleep(args.watch)
            continue
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            render(reps, extra, news, overall, args)
        print(buf.getvalue(), end="")
        if args.html:
            write_html(buf.getvalue(), args.watch)

        items = [(r["tf"], l, t, f"{r['tf']}:{k}") for r in reps for l, k, t in r["alerts"]] + \
                [("کلی", l, t, f"all:{k}") for l, k, t in extra]
        fresh = [(tf, l, t) for tf, l, t, key in items if l in ("good", "bad", "warn") and seen.get(key) != t]
        for tf, l, t, key in items:
            seen[key] = t
        if fresh:
            log_alerts(fresh)
        if args.watch:
            for tf, l, t in fresh:
                if l in ("good", "bad"):
                    notify(("هشدار خوب ✅" if l == "good" else "هشدار بد ⚠️") + f" · طلا {tf}", t)
            time.sleep(args.watch)
        else:
            break


if __name__ == "__main__":
    main()
