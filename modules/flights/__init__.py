"""AIRSPACE — every aircraft broadcasting ADS-B within 60 nautical miles, on a radar scope."""
import math

import pygame
import requests

from tvkit import text, theme
from tvkit.module import Module

from . import data

RANGE_NM = 60
CX, CY, R = 492, 372, 300
RX0, RX1 = 840, 1250
SPOT_S = 15


def _alt(a):
    if a.on_ground:
        return "on the ground"
    return f"FL{a.alt // 100:03d}" if a.alt >= 18000 else f"{a.alt:,} ft"


def _compass(b):
    return ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"][round(b / 45) % 8]


class Airspace(Module):
    name, title, key = "flights", "AIRSPACE", theme.KEYS["flights"]
    blurb = "Live aircraft overhead, from ADS-B receivers"
    aliases = ("airspace", "radar", "flightradar")
    order = 50

    def start(self, ctx):
        super().start(ctx)
        self.place = ctx.config.place
        self.spot_i, self._spot_t = 0, None
        if self.place:
            lat, lon = self.place.lat, self.place.lon
            url = f"https://api.adsb.lol/v2/point/{lat}/{lon}/{RANGE_NM}"
            self.src = self.source("aircraft", lambda: requests.get(url, timeout=15).json(), 60,
                                   parse=lambda p: data.parse(p, lat, lon), cache=False)

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

    def _xy(self, a):
        r = min(a.dist_nm, RANGE_NM) / RANGE_NM * R
        ang = math.radians(a.bearing)
        return CX + r * math.sin(ang), CY - r * math.cos(ang)

    def draw_static(self, surf):
        self._scope(surf)
        if not self.place:
            text.draw(surf, "No place set", (RX0, 60), "display", 80, theme.BONE)
            text.draw(surf, "Add a [place] with lat and lon to ~/.config/pizero-tv/config.toml.", (RX0, 160),
                      "sans", 20, theme.LICHEN, max_w=RX1 - RX0)
            return
        ac = self.src.value
        if ac is None:
            msg = {"offline": "adsb.lol isn't answering. Aircraft appear when it does.",
                   "waiting": "Listening for aircraft."}.get(self.src.status, "")
            text.draw(surf, "—", (RX0, 30), "display", 150, theme.TIDE)
            for i, line in enumerate(text.wrap(msg, "sans", 20, RX1 - RX0)):
                text.draw(surf, line, (RX0, 210 + i * 28), "sans", 20, theme.LICHEN)
            return
        self._blips(surf, ac)
        self._rail(surf, ac)

    def _scope(self, surf):
        pygame.draw.circle(surf, theme.DEEP, (CX, CY), R)
        for i in range(1, 5):
            r = R * i // 4
            pygame.draw.circle(surf, theme.TIDE, (CX, CY), r, 1)
            text.draw(surf, f"{RANGE_NM * i // 4} nm", (CX + 6, CY - r + 4), "sans", 14, theme.LICHEN)
        for ang in range(0, 360, 30):
            a = math.radians(ang)
            pygame.draw.line(surf, theme.TIDE, (CX + 0.25 * R * math.sin(a), CY - 0.25 * R * math.cos(a)),
                             (CX + R * math.sin(a), CY - R * math.cos(a)), 1)
        for lbl, ang in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
            a = math.radians(ang)
            text.draw(surf, lbl, (CX + (R + 18) * math.sin(a), CY - (R + 18) * math.cos(a)), "sans-600", 18,
                      theme.LICHEN, anchor="center")
        name = self.place.name if self.place else ""
        pygame.draw.circle(surf, self.key, (CX, CY), 4)
        text.draw(surf, name, (CX + 8, CY + 6), "sans", 14, theme.LICHEN, max_w=200)

    def _blips(self, surf, ac):
        spot = self._spot(ac)
        taken = []                      # label rects already placed: skip any label that would collide
        order = ([spot] if spot else []) + [a for a in ac if a is not spot and not a.on_ground]
        for a in ac:
            if a.on_ground:
                x, y = self._xy(a)
                pygame.draw.circle(surf, theme.LICHEN, (int(x), int(y)), 2)
        for a in reversed(order):
            x, y = self._xy(a)
            col = theme.CORAL if a.emergency else (theme.BONE if a is spot else self.key)
            if a.track is not None and a.speed:
                L = 6 + a.speed / 30
                t = math.radians(a.track)
                pygame.draw.line(surf, col, (x, y), (x + L * math.sin(t), y - L * math.cos(t)), 2)
            pygame.draw.rect(surf, col, (x - 3, y - 3, 6, 6))
        for a in order:
            x, y = self._xy(a)
            box = pygame.Rect(x + 6, y - 17, 84, 34)
            if a.dist_nm > RANGE_NM * 0.92 or any(box.colliderect(t) for t in taken):
                continue
            taken.append(box)
            col = theme.CORAL if a.emergency else (theme.BONE if a is spot else self.key)
            text.draw(surf, a.callsign, (x + 8, y - 16), "sans-500", 14, col, max_w=84)
            text.draw(surf, _alt(a), (x + 8, y - 1), "sans", 14, theme.LICHEN, max_w=84)

    def _spot(self, ac):
        near = [a for a in ac if not a.on_ground][:5] or ac[:5]
        return near[self.spot_i % len(near)] if near else None

    def _rail(self, surf, ac):
        airborne = [a for a in ac if not a.on_ground]
        r = text.draw(surf, str(len(airborne)), (RX0 - 4, 24), "display", 150, theme.BONE)
        text.draw(surf, f"aircraft in the air within {RANGE_NM} nautical miles", (RX0, r.bottom - 8), "sans", 20,
                  theme.LICHEN, max_w=RX1 - RX0)
        emerg = [a for a in ac if a.emergency]
        y = r.bottom + 34
        if emerg:
            e = emerg[0]
            text.draw(surf, f"{e.callsign} is squawking {e.squawk}: {e.emergency}", (RX0, y), "sans-600", 20,
                      theme.CORAL, max_w=RX1 - RX0)
            y += 32
        pygame.draw.line(surf, theme.TIDE, (RX0, y), (RX1, y), 1)
        a = self._spot(ac)
        if not a:
            return
        y += 18
        text.draw(surf, "Closest flights, in turn", (RX0, y), "sans", 16, theme.LICHEN)
        text.draw(surf, a.callsign, (RX0 - 2, y + 18), "display", 64, self.key, max_w=RX1 - RX0)
        who = " ".join(x for x in (data.airline(a.callsign), data.type_name(a.type)) if x) or "Unidentified aircraft"
        text.draw(surf, who, (RX0, y + 88), "sans-500", 22, theme.BONE, max_w=RX1 - RX0)
        rows = [("Altitude", _alt(a) + ("" if not a.rate or abs(a.rate) < 300 else
                                        (", climbing" if a.rate > 0 else ", descending"))),
                ("Speed", f"{a.speed:.0f} knots" if a.speed else "—"),
                ("Heading", f"{a.track:.0f}°" if a.track is not None else "—"),
                ("Where", f"{a.dist_nm:.0f} nm {_compass(a.bearing)}"),
                ("Registration", a.reg or "—")]
        for i, (k, v) in enumerate(rows):
            ry = y + 128 + i * 30
            text.draw(surf, k, (RX0, ry), "sans", 18, theme.LICHEN)
            text.draw(surf, v, (RX0 + 130, ry), "sans-500", 18, theme.BONE, max_w=RX1 - RX0 - 130)
        near = [x for x in airborne if x is not a][:3]
        ny = y + 286
        if near and ny < 650:
            text.draw(surf, "Also near: " + ", ".join(f"{x.callsign} {x.dist_nm:.0f} nm" for x in near),
                      (RX0, ny), "sans", 16, theme.LICHEN, max_w=RX1 - RX0)

    def draw_live(self, surf, t):
        # the sweep marks the once-a-minute refresh: one turn per poll
        ang = (t % 60) / 60 * 2 * math.pi
        for k in range(12):
            a = ang - k * 0.03
            col = theme.mix(theme.DEEP, self.key, 0.5 * (1 - k / 12))
            pygame.draw.line(surf, col, (CX, CY), (CX + R * math.sin(a), CY - R * math.cos(a)), 2)
        return False


MODULE = Airspace
