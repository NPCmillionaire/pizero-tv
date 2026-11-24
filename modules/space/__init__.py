"""ORBIT — where the International Space Station is, day and night on Earth, and space weather."""
import collections, math, threading

import pygame
import requests

from tvkit import text, theme, world
from tvkit.module import Module

from . import data

# mission control: the big front screen, telemetry tiles along the top, consoles down the side
ROOM, TILE, EDGE = (5, 12, 26), (10, 24, 46), (40, 74, 118)
BLUE, WHITE, DIM, AMBER, RED = (96, 176, 255), (236, 244, 255), (110, 140, 184), (255, 186, 60), (255, 90, 80)
MAP = (30, 196, 1000, world.height_for(1000))
SIDE_X, SIDE_W = 1046, 204
UA = {"User-Agent": "pizero-tv"}


def _get(url, **params):
    r = requests.get(url, params=params, headers=UA, timeout=20)
    r.raise_for_status()
    return r.json()


class Orbit(Module):
    name, title, key = "space", "ORBIT", theme.KEYS["space"]
    blurb = "The space station's path, day and night, and space weather"
    aliases = ("orbit", "iss")
    order = 60
    fps = 8
    footer_color = DIM

    def start(self, ctx):
        super().start(ctx)
        self.trail = collections.deque(maxlen=600)       # ~100 minutes at 10 s: a full orbit
        self.lock = threading.Lock()
        self.proj = world.Projection(MAP)
        self._map = self._night = None
        self._night_key = None
        self._where = ("", None)
        self.iss = self.source("iss", lambda: _get("https://api.wheretheiss.at/v1/satellites/25544"), 10,
                               parse=self._iss, cache=False)
        self.kp = self.source("kp", lambda: _get("https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"),
                              1800, parse=data.parse_kp)
        self.wind = self.source("wind", lambda: _get("https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json"),
                                300, parse=data.parse_wind)
        self.neo = self.source("neo", lambda: _get("https://api.nasa.gov/neo/rest/v1/feed/today", api_key="DEMO_KEY"),
                               3600, parse=data.parse_neo)

    def _iss(self, p):
        i = data.parse_iss(p)
        with self.lock:
            self.trail.append((i.lon, i.lat))
        if self._where[1] is None or abs(self._where[1][0] - i.lon) + abs(self._where[1][1] - i.lat) > 1.5:
            self._where = (data.where(i.lat, i.lon), (i.lon, i.lat))
        return i

    # -- the control room ----------------------------------------------------------------
    def draw_frame(self, surf):
        surf.fill(ROOM)
        text.draw(surf, "Orbit", (30, 18), "console-700", 40, BLUE)
        text.draw(surf, "International Space Station", (150, 32), "console", 20, DIM)
        x, y, w, h = MAP
        pygame.draw.rect(surf, (3, 8, 18), (x, y, w, h))
        for lon in range(-180, 181, 30):
            px = round(x + (lon + 180) / 360 * w)
            pygame.draw.line(surf, (16, 32, 58), (px, y), (px, y + h), 1)
        for lat in range(-60, 61, 30):
            py = self.proj.to_px(0, lat)[1]
            pygame.draw.line(surf, (16, 32, 58), (x, py), (x + w, py), 1)

    def draw_static(self, surf):
        i = self.iss.value
        self._telemetry(surf, i)
        self._map_layer(surf, i)
        pygame.draw.rect(surf, EDGE, (MAP[0] - 1, MAP[1] - 1, MAP[2] + 2, MAP[3] + 2), 1)
        text.draw(surf, "Ground track, last 100 minutes. Shading is night on Earth; the amber dot is the "
                        "point directly under the sun.", (MAP[0], MAP[1] + MAP[3] + 12), "console", 16, DIM,
                  max_w=MAP[2])
        self._weather(surf)

    def _tile(self, surf, r, label, value, col=WHITE, size=32):
        pygame.draw.rect(surf, TILE, r)
        pygame.draw.rect(surf, EDGE, r, 1)
        pygame.draw.rect(surf, BLUE, (r.left, r.top, 3, r.height))
        text.draw(surf, label, (r.left + 14, r.top + 8), "console", 15, DIM, max_w=r.width - 24)
        text.draw(surf, value, (r.left + 14, r.bottom - 8), "console-700", size, col, anchor="bottomleft",
                  max_w=r.width - 24)

    def _telemetry(self, surf, i):
        y, h = 88, 92
        if i is None:
            msg = {"offline": "The ISS position service isn't answering.",
                   "waiting": "Acquiring the space station."}.get(self.iss.status, "")
            self._tile(surf, pygame.Rect(30, y, 1220, h), "Telemetry", msg, DIM, 28)
            return
        lat = f"{abs(i.lat):.2f}° {'N' if i.lat >= 0 else 'S'}"
        lon = f"{abs(i.lon):.2f}° {'E' if i.lon >= 0 else 'W'}"
        sun = "sunlit" if i.daylight else "in Earth's shadow"
        tiles = [(380, f"Over, {sun}", self._where[0] or "open ocean", BLUE),
                 (190, "Altitude", f"{i.alt_km:,.0f} km", WHITE),
                 (250, "Velocity", f"{i.speed_kmh:,.0f} km/h", WHITE),
                 (190, "Position", lat, WHITE),
                 (190, "", lon, WHITE)]
        x = 30
        gap = (1220 - sum(t[0] for t in tiles)) // (len(tiles) - 1)
        for w, label, value, col in tiles:
            self._tile(surf, pygame.Rect(x, y, w, h), label, value, col)
            x += w + gap

    def draw_live(self, surf, t):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        clock = now.strftime("GMT %j:%H:%M:%S")          # day of year, the way flight controllers write it
        pygame.draw.rect(surf, ROOM, (960, 4, 300, 70))
        text.draw(surf, clock, (1250, 24), "console-700", 28, WHITE, anchor="topright")
        pos = getattr(self, "_pos", None)
        if pos:
            k = (t % 2.0) / 2.0
            pygame.draw.circle(surf, theme.mix(ROOM, BLUE, 1 - k), pos, int(10 + 22 * k), 2)
        return True

    def _map_layer(self, surf, i):
        if self._map is None:
            self._map = world.render(MAP, (22, 48, 82), (54, 96, 150))
        surf.blit(self._map, MAP[:2])
        if i is None:
            return
        key = (round(i.sun_lat, 1), round(i.sun_lon))
        if key != self._night_key:
            self._night, self._night_key = self._render_night(i.sun_lat, i.sun_lon), key
        surf.blit(self._night, MAP[:2])
        # the sun's position: where it is directly overhead
        sx, sy = self.proj.to_px(i.sun_lon, i.sun_lat)
        pygame.draw.circle(surf, AMBER, (sx, sy), 6)
        with self.lock:
            trail = list(self.trail)
        seg = []
        for lon, lat in trail:
            p = self.proj.to_px(lon, lat)
            if seg and abs(p[0] - seg[-1][0]) > MAP[2] / 2:      # wrapped around the date line
                if len(seg) > 1:
                    pygame.draw.lines(surf, theme.mix(ROOM, BLUE, 0.8), False, seg, 2)
                seg = []
            seg.append(p)
        if len(seg) > 1:
            pygame.draw.lines(surf, theme.mix(ROOM, BLUE, 0.8), False, seg, 2)
        self._pos = self.proj.to_px(i.lon, i.lat)
        pygame.draw.circle(surf, BLUE, self._pos, 8)
        pygame.draw.circle(surf, WHITE, self._pos, 8, 2)

    def _render_night(self, sun_lat, sun_lon):
        w, h = MAP[2], MAP[3]
        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        p = world.Projection((0, 0, w, h))
        line = [p.to_px(lon, lat) for lon, lat in data.terminator(sun_lat, sun_lon)]
        dark_edge = h if sun_lat > 0 else 0          # the pole tilted away from the sun is in darkness
        poly = line + [(w, dark_edge), (0, dark_edge)]
        pygame.draw.polygon(layer, (0, 4, 12, 160), poly)
        pygame.draw.lines(layer, (*AMBER, 110), False, line, 1)
        return layer

    def _weather(self, surf):
        y0, h = MAP[1], (MAP[3] - 2 * 10) // 3
        k, wnd, n = self.kp.value, self.wind.value, self.neo.value
        rows = []
        if k:
            lvl, g = data.storm_level(k[-1].kp)
            rows.append(("Geomagnetic Kp", f"{k[-1].kp:.1f}", (g or lvl), RED if g else WHITE))
        else:
            rows.append(("Geomagnetic Kp", "—", "no data yet", DIM))
        if wnd:
            rows.append(("Solar wind", f"{wnd.speed:,.0f}", "km/s" + (f", {wnd.density:.1f} p/cm³" if wnd.density else ""),
                         WHITE))
        else:
            rows.append(("Solar wind", "—", "no data yet", DIM))
        if n:
            a = n[0]
            rows.append(("Closest asteroid", f"{a.lunar:.1f}×", f"Moon's distance: {a.name}", RED if a.hazardous else WHITE))
        else:
            rows.append(("Closest asteroid", "—", "no data yet", DIM))
        for i, (label, big, note, col) in enumerate(rows):
            r = pygame.Rect(SIDE_X, y0 + i * (h + 10), SIDE_W, h)
            pygame.draw.rect(surf, TILE, r)
            pygame.draw.rect(surf, EDGE, r, 1)
            text.draw(surf, label, (r.left + 14, r.top + 10), "console", 16, DIM, max_w=r.width - 24)
            text.draw(surf, big, (r.left + 12, r.top + 28), "console-700", 46, col, max_w=r.width - 24)
            for j, line in enumerate(text.wrap(note, "console", 15, r.width - 24)[:2]):
                text.draw(surf, line, (r.left + 14, r.top + 82 + j * 18), "console", 15, DIM, max_w=r.width - 24)


MODULE = Orbit
