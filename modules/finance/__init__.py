"""MARKETS — US indices, a rotating spotlight stock, sectors and macro, from Yahoo Finance."""
import time

import pygame
import requests

from tvkit import charts, fx, text, theme
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
# business-news station: navy desk, electric-blue bars, green and red numbers, a two-line ticker
DESK, PANEL, RULE = (6, 13, 30), (13, 26, 52), (34, 58, 100)
BLUE, WHITE, DIM = (0, 122, 230), (240, 244, 250), (138, 156, 190)
UP, DOWN, GOLD = (40, 220, 120), (255, 72, 72), (255, 196, 60)
HERO = pygame.Rect(30, 92, 760, 384)
SPOT_BOX = pygame.Rect(806, 92, 444, 384)
LOWER = pygame.Rect(30, 490, 1220, 92)
TICK1, TICK2 = pygame.Rect(0, 598, 1280, 40), pygame.Rect(0, 640, 1280, 34)


def _price(v):
    return f"{v:,.2f}" if v < 10000 else f"{v:,.0f}"


def _signed(v, fmt="{:+,.2f}"):
    return fmt.format(v).replace("-", "−")


def _col(v):
    return UP if v >= 0 else DOWN


def _triangle(surf, v, left, cy, size=16):
    """Up or down marker drawn as a shape (the station fonts have no arrow glyphs). Returns its right edge."""
    h = size * 0.8
    pts = ([(left, cy + h / 2), (left + size, cy + h / 2), (left + size / 2, cy - h / 2)] if v >= 0 else
           [(left, cy - h / 2), (left + size, cy - h / 2), (left + size / 2, cy + h / 2)])
    pygame.draw.polygon(surf, _col(v), pts)
    return left + size


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

    # -- the desk ---------------------------------------------------------------------
    def draw_frame(self, surf):
        surf.fill(DESK)
        pygame.draw.rect(surf, BLUE, (30, 22, 196, 50))
        text.draw(surf, "Markets", (128, 47), "sans-600", 36, WHITE, anchor="center")
        text.draw(surf, time.strftime("%-I:%M %p").lower() + "  " + time.strftime("%A %-d %b"), (1250, 47),
                  "mono-500", 22, DIM, anchor="midright")
        for r in (HERO, SPOT_BOX):
            pygame.draw.rect(surf, PANEL, r)
            pygame.draw.rect(surf, BLUE, (r.left, r.top, r.width, 4))
        pygame.draw.rect(surf, PANEL, LOWER)
        pygame.draw.rect(surf, BLUE, (LOWER.left, LOWER.top, 8, LOWER.height))
        pygame.draw.rect(surf, (2, 6, 16), (0, TICK1.top, 1280, TICK2.bottom - TICK1.top))
        pygame.draw.line(surf, BLUE, (0, TICK1.top), (1280, TICK1.top), 2)

    def draw_static(self, surf):
        q = self.spark.value
        if q is None:
            msg = {"offline": "Yahoo Finance isn't answering. Prices appear when it does.",
                   "waiting": "Fetching prices from Yahoo Finance."}.get(self.spark.status, "")
            text.draw(surf, "S&P 500", (HERO.left + 24, HERO.top + 24), "sans-600", 28, WHITE)
            text.draw(surf, "Stand by", (HERO.left + 20, HERO.top + 70), "sans-600", 110, RULE)
            text.draw(surf, msg, (HERO.left + 24, HERO.top + 220), "sans", 24, DIM, max_w=HERO.width - 48)
            return
        self._hero(surf, q)
        self._spotlight(surf)
        self._sectors(surf, q)
        self._tick_key = None

    def draw_live(self, surf, t):
        q = self.spark.value
        if q is None:
            return False
        if getattr(self, "_tick_key", None) != id(q):
            self._tick_key = id(q)
            self._t1 = fx.Crawl(self._ticker(q, [*INDICES[1:], *[(s, l) for s, l, _ in MACRO]]), "mono-500", 24,
                                WHITE, speed=70, sep="     ")
            self._t2 = fx.Crawl(self._ticker(q, SECTORS), "mono", 20, DIM, speed=46, sep="     ")
        pygame.draw.rect(surf, (2, 6, 16), TICK1.inflate(0, -4).move(0, 2))
        pygame.draw.rect(surf, (2, 6, 16), TICK2)
        self._t1.draw(surf, TICK1.inflate(0, -4).move(0, 2), t)
        self._t2.draw(surf, TICK2, t)
        return True

    def _ticker(self, q, pairs):
        items = []
        for pair in pairs:
            sym, label = pair[0], pair[1]
            v = q.get(sym)
            if v:
                items.append([(f"{label} {_price(v.price)} ", WHITE),
                              (_signed(v.change_pct, "{:+.2f}%"), _col(v.change_pct))])
        return items

    def _hero(self, surf, q):
        spx = q.get("^GSPC")
        x, y = HERO.left + 24, HERO.top + 22
        if not spx:
            text.draw(surf, "No S&P 500 quote in this update.", (x, y + 60), "sans", 24, DIM)
            return
        state = data.market_state(time.time(), spx.trading_period)
        when = time.strftime("%-I:%M %p", time.localtime(spx.market_time)).lower() if spx.market_time else ""
        note = {"open": "Market open", "pre": "Pre-market", "after hours": "After hours",
                "closed": "Market closed"}[state] + (f", last trade {when}" if when else "")
        text.draw(surf, "S&P 500", (x, y), "sans-600", 28, WHITE)
        pill = text.render(note, "sans-500", 18, DESK)
        pygame.draw.rect(surf, UP if state == "open" else GOLD,
                         (HERO.right - 24 - pill.get_width() - 20, y + 2, pill.get_width() + 20, 30), border_radius=15)
        surf.blit(pill, (HERO.right - 34 - pill.get_width(), y + 6))
        r = text.draw(surf, _price(spx.price), (x - 4, y + 34), "sans-600", 100, WHITE)
        tx = _triangle(surf, spx.change, x + 2, r.bottom + 18, 20)
        text.draw(surf, f"{_signed(spx.change)}   {_signed(spx.change_pct, '{:+.2f}%')}", (tx + 12, r.bottom + 18),
                  "mono-500", 30, _col(spx.change), anchor="midleft")
        self._area(surf, pygame.Rect(x, r.bottom + 50, HERO.width - 48, HERO.bottom - r.bottom - 70), spx)

    def _area(self, surf, rect, v):
        vals = [p for p in v.series if p is not None]
        if len(vals) < 2:
            text.draw(surf, "No intraday prices yet.", rect.topleft, "sans", 20, DIM)
            return
        base = v.prev_close if v.prev_close else vals[0]
        lo, hi = min(vals + [base]), max(vals + [base])
        span = (hi - lo) or 1.0
        sy = lambda p: rect.bottom - (p - lo) / span * rect.height
        pts = [(rect.left + i * rect.width / (len(vals) - 1), sy(p)) for i, p in enumerate(vals)]
        col = _col(vals[-1] - base)
        fill = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.polygon(fill, (*col, 46), [(px - rect.left, py - rect.top) for px, py in pts]
                            + [(rect.width, rect.height), (0, rect.height)])
        surf.blit(fill, rect.topleft)
        by = sy(base)
        for bx in range(rect.left, rect.right, 10):
            pygame.draw.line(surf, DIM, (bx, by), (bx + 4, by), 1)
        pygame.draw.lines(surf, col, False, pts, 3)
        text.draw(surf, f"prev close {_price(base)}", (rect.right, by - 4), "mono", 15, DIM, anchor="bottomright")

    def _spotlight(self, surf):
        x, y, w = SPOT_BOX.left + 22, SPOT_BOX.top + 22, SPOT_BOX.width - 44
        cs = self.charts.value
        text.draw(surf, "Spotlight", (x, y), "sans-500", 20, DIM)
        if not cs:
            text.draw(surf, "Loading daily candles.", (x, y + 40), "sans", 22, DIM)
            return
        syms = [s for s in SPOT if s in cs]
        c = cs[syms[self.spot_i % len(syms)]]
        prev = c.closes[-2] if len(c.closes) > 1 else c.prev_close
        pct = data.change_pct(c.price, prev) or 0.0
        text.draw(surf, c.symbol, (x - 2, y + 26), "sans-600", 60, WHITE)
        text.draw(surf, c.name, (x, y + 96), "sans", 18, DIM, max_w=w - 170)
        text.draw(surf, f"${c.price:,.2f}", (x + w, y + 30), "mono-500", 36, WHITE, anchor="topright")
        r = text.draw(surf, _signed(pct, "{:+.2f}%") + " today", (x + w, y + 76), "mono-500", 20, _col(pct),
                  anchor="topright")
        _triangle(surf, pct, r.left - 22, r.centery, 14)
        n = 60
        o, h, l, cl = c.opens[-n:], c.highs[-n:], c.lows[-n:], c.closes[-n:]
        ma = data.moving_average(c.closes, 20)[-n:]
        rng = charts.candles(surf, (x, y + 130, w, 180), o, h, l, cl, up=UP, down=DOWN, ma=ma, ma_color=GOLD)
        span = f", ${rng[0]:,.0f} to ${rng[1]:,.0f}" if rng else ""
        text.draw(surf, f"60 days{span}. Gold is the 20-day average.", (x, y + 322), "sans", 16, DIM,
                  max_w=w - len(syms) * 14 - 16)
        dots_x = x + w - len(syms) * 14
        for i in range(len(syms)):
            col = WHITE if i == self.spot_i % len(syms) else RULE
            pygame.draw.circle(surf, col, (dots_x + i * 14 + 5, y + 332), 4)

    def _sectors(self, surf, q):
        x0 = LOWER.left + 24
        text.draw(surf, "Sectors", (x0, LOWER.top + 14), "sans-600", 26, WHITE)
        text.draw(surf, "today", (x0, LOWER.top + 46), "sans", 20, DIM)
        tw = (LOWER.right - x0 - 130 - 5 * 10) // 6
        for i, (sym, label) in enumerate(SECTORS):
            x = x0 + 130 + i * (tw + 10)
            v = q.get(sym)
            pct = v.change_pct if v else 0.0
            strength = min(1.0, abs(pct) / 2.0)
            fill = theme.mix(PANEL, _col(pct), 0.18 + 0.5 * strength) if v else RULE
            cell = pygame.Rect(x, LOWER.top + 12, tw, LOWER.height - 24)
            pygame.draw.rect(surf, fill, cell)
            text.draw(surf, label, (cell.left + 10, cell.top + 6), "sans-500", 18, WHITE, max_w=tw - 20)
            text.draw(surf, _signed(pct, "{:+.2f}%") if v else "—", (cell.left + 10, cell.bottom - 4), "mono-500",
                      24, WHITE, anchor="bottomleft", max_w=tw - 20)


MODULE = Markets
