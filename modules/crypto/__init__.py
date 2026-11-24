"""CRYPTO — bitcoin up close, the top coins, market totals and sentiment."""
import math

import pygame
import requests

from tvkit import charts, fx, text, theme
from tvkit.module import Module

from . import data

CG = "https://api.coingecko.com/api/v3"
UA = {"User-Agent": "pizero-tv"}
# late-night trading show: black-violet studio, neon sign tubes, loud type
NIGHT_TOP, NIGHT_BOTTOM = (26, 4, 48), (3, 0, 10)
PINK, CYAN, YELLOW, WHITE, HAZE = (255, 46, 170), (0, 228, 255), (255, 228, 0), (255, 255, 255), (150, 120, 190)
UP, DOWN = (0, 255, 150), (255, 60, 96)
CHART = pygame.Rect(48, 352, 700, 120)
GAUGE_C, GAUGE_R = (1020, 300), 170
BOARD_Y = 512


def _get(url, **params):
    r = requests.get(url, params=params, headers=UA, timeout=15)
    r.raise_for_status()
    return r.json()


def _col(v):
    return HAZE if v is None else (UP if v >= 0 else DOWN)


def _pct(v):
    return "—" if v is None else f"{v:+.2f}%".replace("-", "−")


SENTIMENT = [(25, DOWN), (45, (255, 140, 40)), (55, YELLOW), (75, (150, 255, 80)), (101, UP)]


def _sent_color(v):
    return next(c for lim, c in SENTIMENT if v < lim)


class Crypto(Module):
    name, title, key = "crypto", "CRYPTO", theme.KEYS["crypto"]
    blurb = "Crypto after dark: bitcoin, the board, and the market's mood"
    order = 30
    fps = 12
    footer_color = HAZE

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

    # -- the studio ------------------------------------------------------------------
    def draw_frame(self, surf):
        surf.blit(fx.gradient((theme.W, theme.H), NIGHT_TOP, NIGHT_BOTTOM), (0, 0))
        for inset, col in ((6, PINK), (11, theme.mix(PINK, NIGHT_TOP, 0.6))):     # the neon border tube
            pygame.draw.rect(surf, col, (inset, inset, theme.W - 2 * inset, theme.H - 2 * inset), 2, border_radius=18)
        img = fx.glow_text("Crypto after dark", "loud", 30, (255, 170, 225), radius=4, halo=PINK)
        surf.blit(img, (40, 30))

    def draw_static(self, surf):
        coins = self.markets.value
        if not coins:
            msg = {"offline": "CoinGecko isn't answering. Prices appear when it does.",
                   "waiting": "Fetching prices from CoinGecko."}.get(self.markets.status, "")
            surf.blit(fx.glow_text("Stand by", "loud", 110, WHITE, radius=5, halo=CYAN), (40, 150))
            text.draw(surf, msg, (52, 330), "sans", 26, HAZE, max_w=1150)
            return
        btc = next((c for c in coins if c.id == "bitcoin"), coins[0])
        self._hero(surf, btc)
        self._candles(surf)
        self._gauge(surf)
        self._board(surf, [c for c in data.watchable(coins) if c.id != btc.id][:8])

    def draw_live(self, surf, t):
        # the ON AIR lamp breathes; everything else holds still
        a = 0.55 + 0.45 * math.sin(t * 2.4)
        col = theme.mix(NIGHT_TOP, (255, 40, 60), a)
        pygame.draw.circle(surf, col, (1196, 52), 9)
        return True

    def _hero(self, surf, btc):
        text.draw(surf, btc.name, (52, 100), "loud", 26, CYAN)
        price = fx.glow_text(data.money(btc.price), "loud", 96, WHITE, radius=6, halo=PINK)
        if price.get_width() > 720:
            price = pygame.transform.smoothscale(price, (720, int(price.get_height() * 720 / price.get_width())))
        surf.blit(price, (36, 128))
        text.draw(surf, f"{_pct(btc.chg24)} today", (52, 262), "loud", 34, _col(btc.chg24), max_w=420)
        if btc.chg7d is not None:
            text.draw(surf, f"{_pct(btc.chg7d)} this week", (480, 272), "sans-500", 24, _col(btc.chg7d), max_w=270)

    def _candles(self, surf):
        o = self.ohlc.value
        text.draw(surf, "Last 24 hours", (CHART.left, CHART.top - 30), "sans-500", 20, HAZE)
        if not o:
            text.draw(surf, "Loading candles.", CHART.topleft, "sans", 20, HAZE)
            return
        lo, hi = charts.candles(surf, CHART, o.opens, o.highs, o.lows, o.closes, up=UP, down=PINK)
        text.draw(surf, f"{data.money(lo)} to {data.money(hi)}", (CHART.right, CHART.top - 30), "sans", 18, HAZE,
                  anchor="topright")

    def _gauge(self, surf):
        cx, cy = GAUGE_C
        f = self.fng.value
        text.draw(surf, "Fear and greed", (cx, 92), "loud", 24, YELLOW, anchor="midtop")
        for i in range(50):                         # the dial, fear (left) to greed (right)
            a0, a1 = math.pi * (1 - i / 50), math.pi * (1 - (i + 1) / 50) - 0.004
            ro, ri = GAUGE_R, GAUGE_R - 20
            pts = [(cx + ro * math.cos(a0), cy - ro * math.sin(a0)), (cx + ro * math.cos(a1), cy - ro * math.sin(a1)),
                   (cx + ri * math.cos(a1), cy - ri * math.sin(a1)), (cx + ri * math.cos(a0), cy - ri * math.sin(a0))]
            pygame.draw.polygon(surf, theme.mix(NIGHT_TOP, _sent_color(i * 2 + 1), 0.85), pts)
        if not f:
            text.draw(surf, "Loading", (cx, cy - 40), "loud", 30, HAZE, anchor="center")
            return
        now = f[0]
        a = math.pi * (1 - now.value / 100)
        tip = (cx + (GAUGE_R - 30) * math.cos(a), cy - (GAUGE_R - 30) * math.sin(a))
        pygame.draw.line(surf, WHITE, (cx, cy), tip, 5)
        pygame.draw.circle(surf, WHITE, (cx, cy), 10)
        col = _sent_color(now.value)
        surf.blit(img := fx.glow_text(str(now.value), "loud", 64, WHITE, radius=5, halo=col),
                  (cx - img.get_width() // 2, cy + 12))
        text.draw(surf, now.label, (cx, cy + 104), "loud", 26, col, anchor="midtop", max_w=420)
        text.draw(surf, "0 fear", (cx - GAUGE_R, cy + 14), "sans", 16, HAZE, anchor="midtop")
        text.draw(surf, "100 greed", (cx + GAUGE_R, cy + 14), "sans", 16, HAZE, anchor="midtop")
        g = self.glob.value
        if g:
            text.draw(surf, f"All crypto {data.money(g.total_mcap)}, {_pct(g.mcap_change_24h)} today. "
                            f"Bitcoin is {g.btc_dominance:.0f}% of it.", (cx, cy + 148), "sans", 18, HAZE,
                      anchor="midtop", max_w=440)

    def _board(self, surf, coins):
        cols, w, h, gap = 4, 286, 76, 12
        for i, c in enumerate(coins):
            x = 48 + (i % cols) * (w + gap)
            y = BOARD_Y + (i // cols) * (h + gap)
            pygame.draw.rect(surf, theme.mix(NIGHT_BOTTOM, PINK, 0.12), (x, y, w, h), border_radius=10)
            pygame.draw.rect(surf, theme.mix(NIGHT_BOTTOM, CYAN, 0.45), (x, y, w, h), 1, border_radius=10)
            text.draw(surf, c.symbol, (x + 14, y + 10), "loud", 26, YELLOW, max_w=110)
            text.draw(surf, c.name, (x + 14, y + 46), "sans", 16, HAZE, max_w=120)
            text.draw(surf, data.money(c.price), (x + w - 14, y + 10), "mono-500", 24, WHITE, anchor="topright",
                      max_w=w - 140)
            text.draw(surf, _pct(c.chg24), (x + w - 14, y + 44), "mono-500", 20, _col(c.chg24), anchor="topright")


MODULE = Crypto
