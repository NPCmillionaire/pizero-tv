"""MARKETS — US indices, a rotating spotlight stock, sectors and macro, from Yahoo Finance."""
import time

import pygame
import requests

from tvkit import charts, text, theme
from tvkit.module import Module

from . import data

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux aarch64) pizero-tv"}
SPARK_URL = "https://query1.finance.yahoo.com/v7/finance/spark"
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}"
INDICES = [("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq"), ("^DJI", "Dow"), ("^RUT", "Russell 2000")]
MACRO = [("^VIX", "VIX", "{:.2f}"), ("^TNX", "10-year yield", "{:.2f}%"), ("DX-Y.NYB", "Dollar index", "{:.2f}"),
         ("GC=F", "Gold", "${:,.0f}"), ("CL=F", "Crude oil", "${:.2f}")]
SECTORS = [("XLK", "Technology"), ("XLF", "Financials"), ("XLE", "Energy"), ("XLV", "Health care"),
           ("XLY", "Consumer"), ("XLI", "Industrials")]
SPOT = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "TSLA", "META"]
SPOT_S = 30
X0 = 190


def _price(v):
    return f"{v:,.2f}" if v < 10000 else f"{v:,.0f}"


def _signed(v, fmt="{:+,.2f}"):
    return fmt.format(v).replace("-", "−")


def _col(v):
    return theme.SEAGLASS if v >= 0 else theme.CORAL


def fetch_spark():
    syms = [s for s, _ in INDICES] + [s for s, _, _ in MACRO] + [s for s, _ in SECTORS]
    r = requests.get(SPARK_URL, params={"symbols": ",".join(syms), "range": "1d", "interval": "15m"},
                     headers=UA, timeout=15)
    r.raise_for_status()
    return r.json()


def fetch_charts():
    out = {}
    for s in SPOT:
        r = requests.get(CHART_URL.format(s), params={"interval": "1d", "range": "3mo"}, headers=UA, timeout=15)
        if r.ok:
            out[s] = r.json()
        time.sleep(1.0)
    return out


class Markets(Module):
    name, title, key = "finance", "MARKETS", theme.KEYS["finance"]
    blurb = "US indices, sectors and a rotating spotlight stock"
    aliases = ("markets", "stocks")
    order = 20

    def start(self, ctx):
        super().start(ctx)
        self.spark = self.source("spark", fetch_spark, 120, parse=data.parse_spark)
        self.charts = self.source("charts", fetch_charts, 900, parse=data.parse_charts)
        self.spot_i, self._spot_t = 0, None

    def update(self, now):
        changed = super().update(now)
        if self._spot_t is None:
            self._spot_t = now
        elif now - self._spot_t >= SPOT_S:
            self.spot_i, self._spot_t, changed = self.spot_i + 1, now, True
        return changed

    def on_key(self, event):
        if event.key in (pygame.K_SPACE, pygame.K_RIGHT):
            self.spot_i += 1
            self.dirty = True

    # ------------------------------------------------------------------------------
    def draw_static(self, surf):
        q = self.spark.value
        if q is None:
            msg = {"offline": "Yahoo Finance isn't answering. Prices appear when it does.",
                   "waiting": "Fetching prices from Yahoo Finance."}.get(self.spark.status, "")
            text.draw(surf, "S&P 500", (X0, 40), "sans-500", 22, theme.LICHEN)
            text.draw(surf, "—", (X0 - 6, 64), "display", 170, theme.TIDE)
            text.draw(surf, msg, (X0, 300), "sans", 24, theme.LICHEN, max_w=1000)
            return
        self._hero(surf, q)
        self._indices(surf, q)
        self._spotlight(surf)
        self._sectors(surf, q)
        self._macro(surf, q)

    def _hero(self, surf, q):
        spx = q.get("^GSPC")
        if not spx:
            return
        text.draw(surf, "S&P 500", (X0, 34), "sans-500", 22, theme.BONE)
        state = data.market_state(time.time(), spx.trading_period)
        when = time.strftime("%-I:%M %p", time.localtime(spx.market_time)).lower() if spx.market_time else ""
        note = {"open": "Market open", "pre": "Pre-market", "after hours": "After hours",
                "closed": "Market closed"}[state] + (f", last trade {when}" if when else "")
        text.draw(surf, note, (X0 + 110, 37), "sans", 20, theme.LICHEN, max_w=440)
        r = text.draw(surf, _price(spx.price), (X0 - 6, 58), "display", 168, theme.BONE)
        text.draw(surf, f"{_signed(spx.change)}  {_signed(spx.change_pct, '{:+.2f}%')}", (X0, r.bottom - 6),
                  "display-400", 46, _col(spx.change))
        charts.sparkline(surf, (X0 + 400, 262, 170, 46), spx.series, _col(spx.change), baseline=spx.prev_close)

    def _indices(self, surf, q):
        y = 330
        pygame.draw.line(surf, theme.TIDE, (X0, y - 10), (760, y - 10), 1)
        colw = 190
        for i, (sym, label) in enumerate(INDICES[1:]):
            x = X0 + i * colw
            v = q.get(sym)
            text.draw(surf, label, (x, y), "sans-500", 20, theme.BONE, max_w=colw - 16)
            if not v:
                text.draw(surf, "no data", (x, y + 30), "sans", 18, theme.LICHEN)
                continue
            text.draw(surf, _price(v.price), (x, y + 26), "display-600", 40, theme.BONE, max_w=colw - 16)
            text.draw(surf, _signed(v.change_pct, "{:+.2f}%"), (x, y + 72), "sans-500", 20, _col(v.change_pct))
            charts.sparkline(surf, (x + 80, y + 76, colw - 100, 20), v.series, _col(v.change_pct), width=1)

    def _spotlight(self, surf):
        x, y, w = 800, 34, 450
        cs = self.charts.value
        if not cs:
            text.draw(surf, "Spotlight", (x, y), "sans-500", 22, theme.BONE)
            text.draw(surf, "Loading daily candles.", (x, y + 34), "sans", 20, theme.LICHEN)
            return
        syms = [s for s in SPOT if s in cs]
        c = cs[syms[self.spot_i % len(syms)]]
        prev = c.closes[-2] if len(c.closes) > 1 else c.prev_close
        pct = data.change_pct(c.price, prev) or 0.0
        text.draw(surf, c.symbol, (x, y - 2), "display", 54, self.key)
        text.draw(surf, c.name, (x + 4, y + 56), "sans", 18, theme.LICHEN, max_w=w - 170)
        text.draw(surf, f"${c.price:,.2f}", (x + w, y), "display-600", 44, theme.BONE, anchor="topright")
        text.draw(surf, _signed(pct, "{:+.2f}%") + " today", (x + w, y + 50), "sans-500", 18, _col(pct),
                  anchor="topright")
        n = 60
        o, h, l, cl = c.opens[-n:], c.highs[-n:], c.lows[-n:], c.closes[-n:]
        ma = data.moving_average(c.closes, 20)[-n:]
        rect = (x, y + 100, w, 170)
        rng = charts.candles(surf, rect, o, h, l, cl, ma=ma)
        span = f", ${rng[0]:,.0f} to ${rng[1]:,.0f}" if rng else ""
        text.draw(surf, f"60 days{span}. Amber is the 20-day average.", (x, y + 280), "sans", 16,
                  theme.LICHEN, max_w=w - len(syms) * 14 - 16)
        dots_x = x + w - len(syms) * 14
        for i in range(len(syms)):
            col = self.key if i == self.spot_i % len(syms) else theme.TIDE
            pygame.draw.circle(surf, col, (dots_x + i * 14 + 5, y + 289), 4)

    def _sectors(self, surf, q):
        y, h = 474, 100
        text.draw(surf, "Sectors today", (X0, y - 30), "sans-500", 20, theme.BONE)
        tw = (1250 - X0 - 5 * 8) // 6
        for i, (sym, label) in enumerate(SECTORS):
            x = X0 + i * (tw + 8)
            v = q.get(sym)
            pct = v.change_pct if v else 0.0
            strength = min(1.0, abs(pct) / 2.0)
            fill = theme.mix(theme.GROUND, _col(pct), 0.12 + 0.5 * strength) if v else theme.TIDE
            pygame.draw.rect(surf, fill, (x, y, tw, h))
            text.draw(surf, label, (x + 12, y + 10), "sans-500", 20, theme.BONE, max_w=tw - 24)
            text.draw(surf, _signed(pct, "{:+.2f}%") if v else "—", (x + 12, y + 38), "display-600", 44,
                      theme.BONE, max_w=tw - 24)
            text.draw(surf, sym, (x + tw - 10, y + h - 8), "sans", 14, theme.mix(fill, theme.BONE, 0.55),
                      anchor="bottomright")

    def _macro(self, surf, q):
        y = 604
        colw = (1250 - X0) // len(MACRO)
        for i, (sym, label, fmt) in enumerate(MACRO):
            x = X0 + i * colw
            v = q.get(sym)
            text.draw(surf, label, (x, y), "sans", 18, theme.LICHEN, max_w=colw - 10)
            if v:
                r = text.draw(surf, fmt.format(v.price), (x, y + 22), "display-600", 40, theme.BONE, max_w=colw - 10)
                text.draw(surf, _signed(v.change_pct, "{:+.2f}%"), (x, y + 68), "sans", 16, _col(v.change_pct))


MODULE = Markets
