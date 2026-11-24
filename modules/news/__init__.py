"""SIGNAL — the planet shaking and the internet talking: USGS earthquakes and Hacker News."""
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pygame
import requests

from tvkit import fx, text, theme, world
from tvkit.module import Module

from . import data

# a breaking-news bulletin: red banner, studio navy, a city clock strip and a crawl
STUDIO_TOP, STUDIO_BOTTOM = (10, 16, 40), (4, 6, 16)
RED, DARKRED, WHITE, DIM, GOLD = (214, 22, 32), (130, 8, 16), (250, 250, 250), (150, 160, 190), (255, 200, 60)
MAP = (30, 168, 640, world.height_for(640))
RX0, RX1 = 706, 1250
CRAWL = pygame.Rect(0, 628, 1280, 46)
HN = "https://hacker-news.firebaseio.com/v0"
CLOCKS = [("New York", "America/New_York"), ("London", "Europe/London"), ("Tokyo", "Asia/Tokyo"),
          ("Sydney", "Australia/Sydney")]


def fetch_hn():
    ids = requests.get(f"{HN}/topstories.json", timeout=15).json()[:9]
    return [requests.get(f"{HN}/item/{i}.json", timeout=15).json() for i in ids]


def _mag_color(m):
    return (255, 70, 60) if m >= 6 else GOLD if m >= 4.5 else (170, 180, 205)


class Signal(Module):
    name, title, key = "news", "SIGNAL", theme.KEYS["news"]
    blurb = "Earthquakes around the world and what the internet is reading"
    aliases = ("signal", "quakes")
    order = 70
    fps = 20
    footer_color = DIM

    def start(self, ctx):
        super().start(ctx)
        self.quakes = self.source("quakes", lambda: requests.get(
            "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson", timeout=20).json(), 300,
            parse=data.parse_quakes)
        self.hn = self.source("hn", fetch_hn, 600, parse=data.parse_hn)
        self.proj = world.Projection(MAP)
        self._map = None
        self._minute = None
        self._big = None
        self._crawl = self._crawl_key = None

    def update(self, now):
        changed = super().update(now)
        m = time.strftime("%H:%M")
        if m != self._minute:
            self._minute, changed = m, True
        return changed

    # -- the bulletin ------------------------------------------------------------------
    def draw_frame(self, surf):
        surf.blit(fx.gradient((theme.W, theme.H), STUDIO_TOP, STUDIO_BOTTOM), (0, 0))
        pygame.draw.rect(surf, RED, (0, 20, 1280, 74))
        pygame.draw.rect(surf, DARKRED, (0, 20, 236, 74))
        text.draw(surf, "Bulletin", (118, 57), "bulletin", 46, WHITE, anchor="center")
        pygame.draw.rect(surf, (2, 4, 12), CRAWL)
        pygame.draw.rect(surf, RED, (0, CRAWL.top, 150, CRAWL.height))
        text.draw(surf, "Quakes", (75, CRAWL.centery), "bulletin", 26, WHITE, anchor="center")

    def draw_static(self, surf):
        self._headline(surf)
        self._clocks(surf)
        self._quakes(surf)
        self._stories(surf)

    def draw_live(self, surf, t):
        q = self.quakes.value
        if q:
            if self._crawl_key != id(q):
                now = datetime.now(timezone.utc)
                items = [[(f"M{k.mag:.1f} ", _mag_color(k.mag)),
                          (f"{k.place}, {data.ago((now - k.time).total_seconds())}", WHITE)]
                         for k in sorted(q, key=lambda x: x.time, reverse=True)[:30]]
                self._crawl, self._crawl_key = fx.Crawl(items, "sans-500", 24, WHITE, speed=85, sep="      "), id(q)
            band = pygame.Rect(150, CRAWL.top, 1130, CRAWL.height)
            pygame.draw.rect(surf, (2, 4, 12), band)
            self._crawl.draw(surf, band.inflate(-20, 0), t)
        if self._big:
            k = (t % 2.5) / 2.5
            pygame.draw.circle(surf, theme.mix(STUDIO_TOP, (255, 70, 60), 1 - k), self._big, int(6 + 26 * k), 2)
        return bool(q) or bool(self._big)

    def _headline(self, surf):
        q = self.quakes.value
        x = 256
        if not q:
            msg = {"offline": "USGS isn't answering.", "waiting": "Fetching earthquakes from USGS."}.get(
                self.quakes.status, "")
            text.draw(surf, msg or "No earthquakes reported", (x, 57), "bulletin", 34, WHITE, anchor="midleft",
                      max_w=1000)
            return
        s = data.strongest(q)
        now = datetime.now(timezone.utc)
        r = text.draw(surf, f"Magnitude {s.mag:.1f}", (x, 24), "bulletin", 40, WHITE)
        text.draw(surf, s.place, (r.right + 20, 30), "bulletin", 30, WHITE, max_w=1250 - r.right - 20)
        extra = f"Strongest in two days. {data.ago((now - s.time).total_seconds())}, {s.depth_km:.0f} km deep"
        if s.tsunami:
            extra += ", tsunami message issued"
        text.draw(surf, extra + ".", (r.right + 22, 66), "sans-500", 18, (255, 220, 220), max_w=1250 - r.right - 22)

    def _quakes(self, surf):
        q = self.quakes.value
        now = datetime.now(timezone.utc)
        if self._map is None:
            self._map = world.render(MAP, (30, 42, 80), (60, 78, 130))
        surf.blit(self._map, MAP[:2])
        if not q:
            return
        for k in sorted(q, key=lambda x: x.mag):
            p = self.proj.to_px(k.lon, k.lat)
            age_h = (now - k.time).total_seconds() / 3600
            rad = max(2, int((k.mag - 2) * 3))
            col = _mag_color(k.mag) if age_h < 24 else theme.mix(STUDIO_TOP, _mag_color(k.mag), 0.5)
            pygame.draw.circle(surf, col, p, rad, 0 if age_h < 6 else 1)
        s = data.strongest(q)
        self._big = self.proj.to_px(s.lon, s.lat)
        y = MAP[1] + MAP[3] + 12
        text.draw(surf, f"{len(q)} quakes of magnitude 2.5 or more in two days. Filled dots are under six hours old.",
                  (MAP[0], y), "sans", 16, DIM, max_w=MAP[2])
        for i, k in enumerate(sorted(q, key=lambda x: x.mag, reverse=True)[1:5]):
            ry = y + 30 + i * 36
            text.draw(surf, f"M{k.mag:.1f}", (MAP[0], ry), "bulletin", 26, _mag_color(k.mag))
            text.draw(surf, k.place, (MAP[0] + 70, ry + 4), "sans-500", 20, WHITE, max_w=430)
            text.draw(surf, data.ago((now - k.time).total_seconds()), (MAP[0] + MAP[2], ry + 4), "sans", 18,
                      DIM, anchor="topright")

    def _clocks(self, surf):
        y = 108
        colw = 1220 // len(CLOCKS)
        for i, (city, tz) in enumerate(CLOCKS):
            t = datetime.now(ZoneInfo(tz))
            x = 30 + i * colw
            r = text.draw(surf, t.strftime("%H:%M"), (x, y), "bulletin", 34, WHITE)
            text.draw(surf, city, (r.right + 10, y + 14), "sans-500", 18, DIM, max_w=colw - r.width - 20)
            if i:
                pygame.draw.line(surf, (40, 50, 90), (x - 16, y + 4), (x - 16, y + 40), 1)

    def _stories(self, surf):
        text.draw(surf, "What the internet is reading", (RX0, MAP[1] - 4), "bulletin", 30, WHITE)
        text.draw(surf, "Hacker News front page", (RX1, MAP[1] + 8), "sans", 16, DIM, anchor="topright")
        s = self.hn.value
        if not s:
            msg = {"offline": "Hacker News isn't answering.", "waiting": "Fetching the front page."}.get(
                self.hn.status, "")
            text.draw(surf, msg, (RX0, MAP[1] + 50), "sans", 20, DIM)
            return
        y = MAP[1] + 48
        now = time.time()
        for n, st in enumerate(s, 1):                       # the front page's own ranking
            lines = text.wrap(st.title, "sans-500", 21, RX1 - RX0 - 48)[:2]
            if y + 26 * len(lines) + 22 > CRAWL.top - 8:
                break
            text.draw(surf, str(n), (RX0 + 30, y - 2), "bulletin", 30, RED, anchor="topright")
            for line in lines:
                text.draw(surf, line, (RX0 + 48, y), "sans-500", 21, WHITE, max_w=RX1 - RX0 - 48)
                y += 26
            text.draw(surf, f"{st.score:,} points, {st.comments:,} comments, {st.domain}, {data.ago(now - st.time)}",
                      (RX0 + 48, y), "sans", 16, DIM, max_w=RX1 - RX0 - 48)
            y += 32


MODULE = Signal
