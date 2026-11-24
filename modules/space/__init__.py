"""ORBIT — where the International Space Station is, day and night on Earth, and space weather."""
import collections, math, threading

import pygame
import requests

from tvkit import text, theme, world
from tvkit.module import Module

from . import data

X0 = 190
MAP = (190, 196, 1060, world.height_for(1060))
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

    # ------------------------------------------------------------------------------
    def draw_static(self, surf):
        i = self.iss.value
        self._hero(surf, i)
        self._map_layer(surf, i)
        self._weather(surf)

    def _hero(self, surf, i):
        text.draw(surf, "International Space Station", (X0, 28), "sans-500", 22, theme.BONE)
        if i is None:
            msg = {"offline": "The ISS position service isn't answering.",
                   "waiting": "Finding the space station."}.get(self.iss.status, "")
            text.draw(surf, msg, (X0, 70), "sans", 24, theme.LICHEN)
            return
        place = self._where[0]
        light = "in daylight" if i.daylight else "in Earth's shadow"
        r = text.draw(surf, f"Over {place}", (X0 - 2, 52), "display", 84, self.key, max_w=700)
        text.draw(surf, f"Flying {light}, {i.alt_km:,.0f} km up. One lap of Earth takes about 92 minutes.",
                  (X0, r.bottom + 2), "sans", 22, theme.LICHEN, max_w=700)
        text.draw(surf, f"{i.speed_kmh:,.0f}", (1250, 20), "display", 110, theme.BONE, anchor="topright")
        text.draw(surf, "km/h", (1250, 128), "sans", 18, theme.LICHEN, anchor="topright")

    def _map_layer(self, surf, i):
        if self._map is None:
            self._map = world.render(MAP, (26, 54, 66), (34, 66, 80))
        surf.blit(self._map, MAP[:2])
        if i is None:
            return
        key = (round(i.sun_lat, 1), round(i.sun_lon))
        if key != self._night_key:
            self._night, self._night_key = self._render_night(i.sun_lat, i.sun_lon), key
        surf.blit(self._night, MAP[:2])
        # the sun's position: where it is directly overhead
        sx, sy = self.proj.to_px(i.sun_lon, i.sun_lat)
        pygame.draw.circle(surf, theme.SODIUM, (sx, sy), 6)
        with self.lock:
            trail = list(self.trail)
        seg = []
        for lon, lat in trail:
            p = self.proj.to_px(lon, lat)
            if seg and abs(p[0] - seg[-1][0]) > MAP[2] / 2:      # wrapped around the date line
                if len(seg) > 1:
                    pygame.draw.lines(surf, theme.mix(theme.GROUND, self.key, 0.7), False, seg, 2)
                seg = []
            seg.append(p)
        if len(seg) > 1:
            pygame.draw.lines(surf, theme.mix(theme.GROUND, self.key, 0.7), False, seg, 2)
        self._pos = self.proj.to_px(i.lon, i.lat)
        pygame.draw.circle(surf, self.key, self._pos, 8)
        pygame.draw.circle(surf, theme.BONE, self._pos, 8, 2)

    def _render_night(self, sun_lat, sun_lon):
        w, h = MAP[2], MAP[3]
        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        p = world.Projection((0, 0, w, h))
        line = [p.to_px(lon, lat) for lon, lat in data.terminator(sun_lat, sun_lon)]
        dark_edge = h if sun_lat > 0 else 0          # the pole tilted away from the sun is in darkness
        poly = line + [(w, dark_edge), (0, dark_edge)]
        pygame.draw.polygon(layer, (2, 8, 12, 150), poly)
        pygame.draw.lines(layer, (*self.key, 90), False, line, 1)
        return layer

    def _weather(self, surf):
        y = MAP[1] + MAP[3] + 16
        colw = 340
        k = self.kp.value
        if k:
            lvl, g = data.storm_level(k[-1].kp)
            text.draw(surf, "Geomagnetic activity", (X0, y), "sans", 16, theme.LICHEN)
            text.draw(surf, f"Kp {k[-1].kp:.1f}, {lvl}" + (f" ({g})" if g else ""), (X0, y + 20), "sans-500", 22,
                      theme.CORAL if g else theme.BONE, max_w=colw - 20)
        wnd = self.wind.value
        if wnd:
            text.draw(surf, "Solar wind", (X0 + colw, y), "sans", 16, theme.LICHEN)
            text.draw(surf, f"{wnd.speed:,.0f} km/s" + (f", {wnd.density:.1f} protons/cm³" if wnd.density else ""),
                      (X0 + colw, y + 20), "sans-500", 22, theme.BONE, max_w=colw - 20)
        n = self.neo.value
        if n:
            a = n[0]
            text.draw(surf, "Closest asteroid today", (X0 + 2 * colw, y), "sans", 16, theme.LICHEN)
            text.draw(surf, f"{a.name}, {a.lunar:.1f}× the Moon's distance", (X0 + 2 * colw, y + 20), "sans-500", 22,
                      theme.CORAL if a.hazardous else theme.BONE, max_w=1250 - X0 - 2 * colw)

    def draw_live(self, surf, t):
        pos = getattr(self, "_pos", None)
        if pos:
            k = (t % 2.0) / 2.0
            pygame.draw.circle(surf, theme.mix(theme.GROUND, self.key, 1 - k), pos, int(10 + 22 * k), 2)
        return False      # a slow ping reads fine at the idle frame rate


MODULE = Orbit
