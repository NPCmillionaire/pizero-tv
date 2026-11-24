"""Yahoo Finance spark + chart payloads → quotes and candles."""
from dataclasses import dataclass, field


@dataclass
class Quote:
    symbol: str
    name: str
    price: float
    change: float
    change_pct: float
    day_hi: float | None
    day_lo: float | None
    prev_close: float | None
    series: list = field(default_factory=list)
    trading_period: dict | None = None
    market_time: int | None = None


@dataclass
class Candles:
    symbol: str
    name: str
    price: float
    prev_close: float | None
    opens: list
    highs: list
    lows: list
    closes: list
    times: list


def change_pct(price, prev):
    if not prev:
        return None
    return (price - prev) / prev * 100


def parse_spark(payload):
    out = {}
    for item in payload["spark"]["result"]:
        try:
            r = item["response"][0]
            m = r["meta"]
            price = float(m["regularMarketPrice"])
            prev = m.get("chartPreviousClose") or m.get("previousClose")
            chg = m.get("fulldayChange")
            pct = m.get("regularMarketChangePercent", m.get("fulldayChangePercent"))
            if chg is None and prev:
                chg = price - prev
            if pct is None:
                pct = change_pct(price, prev) or 0.0
            closes = [c for c in (r.get("indicators", {}).get("quote", [{}])[0].get("close") or []) if c is not None]
            out[m["symbol"]] = Quote(m["symbol"], m.get("shortName") or m["symbol"], price, float(chg or 0.0),
                                     float(pct), m.get("regularMarketDayHigh"), m.get("regularMarketDayLow"), prev,
                                     closes, m.get("currentTradingPeriod"), m.get("regularMarketTime"))
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    if not out:
        raise ValueError("spark payload had no usable quotes")
    return out


def parse_chart(payload):
    r = payload["chart"]["result"][0]
    m, q = r["meta"], r["indicators"]["quote"][0]
    rows = [(t, o, h, l, c) for t, o, h, l, c in zip(r["timestamp"], q["open"], q["high"], q["low"], q["close"])
            if None not in (o, h, l, c)]
    if not rows:
        raise ValueError("no candles")
    t, o, h, l, c = (list(x) for x in zip(*rows))
    return Candles(m["symbol"], m.get("longName") or m.get("shortName") or m["symbol"],
                   float(m["regularMarketPrice"]), m.get("chartPreviousClose"), o, h, l, c, t)


def parse_charts(payloads):
    out = {}
    for sym, p in payloads.items():
        try:
            out[sym] = parse_chart(p)
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    if not out:
        raise ValueError("no usable charts")
    return out


def market_state(now_ts, tp):
    """'pre' · 'open' · 'after hours' · 'closed' from Yahoo's currentTradingPeriod."""
    if not tp:
        return "closed"
    for key, label in (("regular", "open"), ("pre", "pre"), ("post", "after hours")):
        p = tp.get(key) or {}
        if p.get("start", 0) <= now_ts < p.get("end", 0):
            return label
    return "closed"


def moving_average(xs, n):
    out = []
    for i in range(len(xs)):
        out.append(None if i + 1 < n else sum(xs[i + 1 - n:i + 1]) / n)
    return out
