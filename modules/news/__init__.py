"""SIGNAL — the planet shaking and the internet talking: USGS earthquakes and Hacker News."""
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pygame
import requests

from tvkit import text, theme, world
from tvkit.module import Module

from . import data

X0 = 190
MAP = (190, 214, 620, world.height_for(620))
RX0, RX1 = 850, 1250
HN = "https://hacker-news.firebaseio.com/v0"
CLOCKS = [("New York", "America/New_York"), ("London", "Europe/London"), ("Tokyo", "Asia/Tokyo"),
          ("Sydney", "Australia/Sydney")]


def fetch_hn():
    ids = requests.get(f"{HN}/topstories.json", timeout=15).json()[:9]
    return [requests.get(f"{HN}/item/{i}.json", timeout=15).json() for i in ids]


def _mag_color(m):
    return theme.CORAL if m >= 6 else theme.SODIUM if m >= 4.5 else theme.mix(theme.GROUND, theme.BONE, 0.7)


class Signal(Module):
    name, title, key = "news", "SIGNAL", theme.KEYS["news"]
    blurb = "Earthquakes around the world and what the internet is reading"
    aliases = ("signal", "quakes")
    order = 70

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

    def update(self, now):
        changed = super().update(now)
        m = time.strftime("%H:%M")
        if m != self._minute:
            self._minute, changed = m, True
        return changed

    def draw_static(self, surf):
        self._quakes(surf)
        self._clocks(surf)
        self._stories(surf)

    def _quakes(self, surf):
        q = self.quakes.value
        now = datetime.now(timezone.utc)
        text.draw(surf, "Strongest earthquake in the last two days", (X0, 28), "sans-500", 20, theme.BONE)
        if self._map is None:
            self._map = world.render(MAP, (22, 50, 58), (30, 62, 70))
        surf.blit(self._map, MAP[:2])
        if not q:
            msg = {"offline": "USGS isn't answering.", "waiting": "Fetching earthquakes from USGS."}.get(
                self.quakes.status, "")
            text.draw(surf, msg, (X0, 60), "sans", 22, theme.LICHEN)
            return
        s = data.strongest(q)
        r = text.draw(surf, f"M{s.mag:.1f}", (X0 - 4, 48), "display", 120, _mag_color(s.mag))
        text.draw(surf, s.place, (r.right + 18, 66), "display-400", 40, theme.BONE, max_w=RX0 - r.right - 50)
        extra = f"{data.ago((now - s.time).total_seconds())}, {s.depth_km:.0f} km deep"
        if s.tsunami:
            extra += ", tsunami message issued"
        text.draw(surf, extra, (r.right + 20, 116), "sans", 20, theme.LICHEN, max_w=RX0 - r.right - 50)
        for k in sorted(q, key=lambda x: x.mag):
            p = self.proj.to_px(k.lon, k.lat)
            age_h = (now - k.time).total_seconds() / 3600
            rad = max(2, int((k.mag - 2) * 3))
            col = _mag_color(k.mag) if age_h < 24 else theme.mix(theme.GROUND, _mag_color(k.mag), 0.5)
            pygame.draw.circle(surf, col, p, rad, 0 if age_h < 6 else 1)
        self._big = self.proj.to_px(s.lon, s.lat)
        y = MAP[1] + MAP[3] + 14
        text.draw(surf, f"{len(q)} quakes of magnitude 2.5 or more. Filled dots are under six hours old.",
                  (X0, y), "sans", 16, theme.LICHEN, max_w=MAP[2])
        for i, k in enumerate(sorted(q, key=lambda x: x.mag, reverse=True)[1:5]):
            ry = y + 30 + i * 30
            text.draw(surf, f"M{k.mag:.1f}", (X0, ry), "display-600", 26, _mag_color(k.mag))
            text.draw(surf, k.place, (X0 + 70, ry + 3), "sans", 18, theme.BONE, max_w=420)
            text.draw(surf, data.ago((now - k.time).total_seconds()), (X0 + MAP[2], ry + 3), "sans", 18,
                      theme.LICHEN, anchor="topright")

    def _clocks(self, surf):
        y = 664
        colw = MAP[2] // len(CLOCKS)
        for i, (city, tz) in enumerate(CLOCKS):
            t = datetime.now(ZoneInfo(tz))
            x = X0 + i * colw
            r = text.draw(surf, t.strftime("%H:%M"), (x, y - 8), "display-600", 34, theme.BONE)
            text.draw(surf, city, (r.right + 8, y + 6), "sans", 16, theme.LICHEN, max_w=colw - r.width - 14)

    def _stories(self, surf):
        text.draw(surf, "Hacker News, front page", (RX0, 28), "sans-500", 20, theme.BONE)
        s = self.hn.value
        if not s:
            msg = {"offline": "Hacker News isn't answering.", "waiting": "Fetching the front page."}.get(
                self.hn.status, "")
            text.draw(surf, msg, (RX0, 64), "sans", 20, theme.LICHEN)
            return
        y = 66
        now = time.time()
        for st in s:
            lines = text.wrap(st.title, "sans-500", 21, RX1 - RX0)[:2]
            if y + 26 * len(lines) + 24 > 686:
                break
            for line in lines:
                text.draw(surf, line, (RX0, y), "sans-500", 21, theme.BONE, max_w=RX1 - RX0)
                y += 26
            text.draw(surf, f"{st.score:,} points, {st.comments:,} comments, {st.domain}, {data.ago(now - st.time)}",
                      (RX0, y), "sans", 16, theme.LICHEN, max_w=RX1 - RX0)
            y += 34

    def draw_live(self, surf, t):
        if self._big:
            k = (t % 2.5) / 2.5
            pygame.draw.circle(surf, theme.mix(theme.GROUND, theme.CORAL, 1 - k), self._big, int(6 + 26 * k), 2)
        return False


MODULE = Signal
