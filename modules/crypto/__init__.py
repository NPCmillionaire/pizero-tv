"""CRYPTO — bitcoin up close, the top coins, market totals and sentiment."""
import math

import pygame
import requests

from tvkit import charts, text, theme
from tvkit.module import Module

from . import data

CG = "https://api.coingecko.com/api/v3"
UA = {"User-Agent": "pizero-tv"}
X0, RX = 190, 800


def _get(url, **params):
    r = requests.get(url, params=params, headers=UA, timeout=15)
    r.raise_for_status()
    return r.json()


def _col(v):
    return theme.LICHEN if v is None else (theme.SEAGLASS if v >= 0 else theme.CORAL)


def _pct(v):
    return "—" if v is None else f"{v:+.2f}%".replace("-", "−")


SENTIMENT = [(25, theme.CORAL), (45, theme.SODIUM), (55, theme.LICHEN), (75, (160, 214, 140)), (101, theme.SEAGLASS)]


def _sent_color(v):
    return next(c for lim, c in SENTIMENT if v < lim)


class Crypto(Module):
    name, title, key = "crypto", "CRYPTO", theme.KEYS["crypto"]
    blurb = "Bitcoin up close, the top coins, and the market's mood"
    order = 30

    def start(self, ctx):
        super().start(ctx)
        self.markets = self.source("markets", lambda: _get(
            CG + "/coins/markets", vs_currency="usd", order="market_cap_desc", per_page=25, page=1,
            sparkline="false", price_change_percentage="24h,7d"), 120, parse=data.parse_markets)
        self.glob = self.source("global", lambda: _get(CG + "/global"), 300, parse=data.parse_global)
        self.ohlc = self.source("ohlc", lambda: _get(CG + "/coins/bitcoin/ohlc", vs_currency="usd", days="1"),
                                300, parse=data.parse_ohlc)
        self.fng = self.source("fng", lambda: _get("https://api.alternative.me/fng/", limit=30), 1800,
                               parse=data.parse_fng)

    def draw_static(self, surf):
        coins = self.markets.value
        if not coins:
            msg = {"offline": "CoinGecko isn't answering. Prices appear when it does.",
                   "waiting": "Fetching prices from CoinGecko."}.get(self.markets.status, "")
            text.draw(surf, "Bitcoin", (X0, 34), "sans-500", 22, theme.LICHEN)
            text.draw(surf, "—", (X0 - 6, 58), "display", 168, theme.TIDE)
            text.draw(surf, msg, (X0, 300), "sans", 24, theme.LICHEN, max_w=1000)
            return
        btc = next((c for c in coins if c.id == "bitcoin"), coins[0])
        self._hero(surf, btc)
        self._candles(surf)
        self._watchlist(surf, [c for c in data.watchable(coins) if c.id != btc.id][:8])
        self._market(surf)
        self._sentiment(surf)

    def _hero(self, surf, btc):
        text.draw(surf, btc.name, (X0, 34), "sans-500", 22, theme.BONE)
        r = text.draw(surf, data.money(btc.price), (X0 - 6, 58), "display", 168, theme.BONE, max_w=580)
        text.draw(surf, f"{_pct(btc.chg24)} in 24 hours", (X0, r.bottom - 6), "display-400", 44, _col(btc.chg24),
                  max_w=560)
        if btc.chg7d is not None:
            text.draw(surf, f"{_pct(btc.chg7d)} over 7 days", (X0, r.bottom + 46), "sans", 20, theme.LICHEN)

    def _candles(self, surf):
        x, y, w, h = RX, 54, 450, 210
        text.draw(surf, "Bitcoin, last 24 hours", (x, 26), "sans-500", 20, theme.BONE)
        o = self.ohlc.value
        if not o:
            text.draw(surf, "Loading candles.", (x, y + 10), "sans", 18, theme.LICHEN)
            return
        lo, hi = charts.candles(surf, (x, y, w, h), o.opens, o.highs, o.lows, o.closes)
        text.draw(surf, f"Range {data.money(lo)} to {data.money(hi)}, 30-minute candles", (x, y + h + 10), "sans", 16,
                  theme.LICHEN, max_w=w)

    def _watchlist(self, surf, coins):
        y0 = 352
        pygame.draw.line(surf, theme.TIDE, (X0, y0 - 16), (760, y0 - 16), 1)
        for i, c in enumerate(coins):
            y = y0 + i * 42
            text.draw(surf, c.symbol, (X0, y), "display-600", 30, self.key, max_w=90)
            text.draw(surf, c.name, (X0 + 92, y + 6), "sans", 18, theme.LICHEN, max_w=150)
            text.draw(surf, data.money(c.price), (X0 + 390, y + 2), "display-600", 30, theme.BONE, anchor="topright")
            text.draw(surf, _pct(c.chg24), (X0 + 490, y + 6), "sans-500", 18, _col(c.chg24), anchor="topright")
            # where the price sits in its 24 h range
            bx, bw = X0 + 504, 66
            f = data.range_position(c.price, c.lo24, c.hi24)
            pygame.draw.line(surf, theme.TIDE, (bx, y + 17), (bx + bw, y + 17), 3)
            pygame.draw.circle(surf, theme.BONE, (int(bx + f * bw), y + 17), 4)
        text.draw(surf, "Dots show where each price sits in its 24-hour range", (X0, y0 + len(coins) * 42),
                  "sans", 14, theme.LICHEN, max_w=570)

    def _market(self, surf):
        g = self.glob.value
        x, y = RX, 336
        if not g:
            return
        text.draw(surf, "All crypto", (x, y), "sans", 18, theme.LICHEN)
        text.draw(surf, data.money(g.total_mcap), (x, y + 20), "display-600", 44, theme.BONE)
        text.draw(surf, f"{_pct(g.mcap_change_24h)} today", (x, y + 70), "sans-500", 18, _col(g.mcap_change_24h))
        text.draw(surf, "Traded in 24 h", (x + 240, y), "sans", 18, theme.LICHEN)
        text.draw(surf, data.money(g.volume), (x + 240, y + 20), "display-600", 44, theme.BONE)
        # dominance bar
        by, bw = y + 108, 450
        btc_w = int(bw * g.btc_dominance / 100)
        eth_w = int(bw * g.eth_dominance / 100)
        pygame.draw.rect(surf, self.key, (x, by, btc_w, 10))
        pygame.draw.rect(surf, theme.LICHEN, (x + btc_w, by, eth_w, 10))
        pygame.draw.rect(surf, theme.TIDE, (x + btc_w + eth_w, by, bw - btc_w - eth_w, 10))
        text.draw(surf, f"Bitcoin {g.btc_dominance:.1f}% of all value, ether {g.eth_dominance:.1f}%",
                  (x, by + 16), "sans", 16, theme.LICHEN, max_w=bw)

    def _sentiment(self, surf):
        f = self.fng.value
        x, y = RX, 492
        if not f:
            return
        now = f[0]
        col = _sent_color(now.value)
        text.draw(surf, "Fear and greed", (x, y), "sans", 18, theme.LICHEN)
        r = text.draw(surf, str(now.value), (x - 2, y + 18), "display", 96, col)
        text.draw(surf, now.label, (r.right + 14, y + 40), "display-400", 40, col, max_w=450 - r.width - 20)
        text.draw(surf, "0 is extreme fear, 100 extreme greed", (r.right + 14, y + 86), "sans", 14, theme.LICHEN,
                  max_w=450 - r.width - 20)
        # last 30 days, oldest left
        hist = list(reversed(f[:30]))
        bx, bw, bh, base = x, 450, 40, y + 168
        step = bw / max(1, len(hist))
        for i, s in enumerate(hist):
            hh = max(2, s.value / 100 * bh)
            pygame.draw.rect(surf, _sent_color(s.value), (bx + i * step, base - hh, max(2, step - 3), hh))
        text.draw(surf, "Last 30 days", (x + bw, base - bh - 18), "sans", 14, theme.LICHEN, anchor="topright")


MODULE = Crypto
