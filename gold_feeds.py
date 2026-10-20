# -*- coding: utf-8 -*-
"""اخبار یاهو فاینانس را به اخبار گوگل اضافه می‌کند (تکراری‌ها حذف می‌شوند)."""
import re
from datetime import datetime, timezone

import gold_news as gn

_orig = gn.fetch_headlines


def _yahoo_items(hours):
    out = []
    try:
        import yfinance as yf
        now = datetime.now(timezone.utc)
        for n in (yf.Ticker("GC=F").news or []):
            c = n.get("content", n)
            title = (c.get("title") or "").strip()
            if not title:
                continue
            ts = c.get("pubDate") or c.get("providerPublishTime")
            try:
                dt = (datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str)
                      else datetime.fromtimestamp(ts, timezone.utc))
                age = (now - dt).total_seconds() / 3600
            except Exception:
                age = 12.0
            if age > hours:
                continue
            link = ((c.get("canonicalUrl") or {}).get("url") or c.get("link") or "")
            src = (c.get("provider") or {}).get("displayName") or c.get("publisher") or "Yahoo Finance"
            out.append(dict(title=title, link=link, source=src, time=None, age_h=max(age, 0.0)))
    except Exception:
        pass
    return out


def _both(hours=24):
    items, err = [], None
    try:
        items = _orig(hours)
    except Exception as e:
        err = e
    seen = {re.sub(r"[^a-z0-9]", "", x["title"].lower())[:60] for x in items}
    for y in _yahoo_items(hours):
        k = re.sub(r"[^a-z0-9]", "", y["title"].lower())[:60]
        if k and k not in seen:
            seen.add(k)
            items.append(y)
    if not items and err:
        raise err
    return items


def install():
    gn.fetch_headlines = _both
