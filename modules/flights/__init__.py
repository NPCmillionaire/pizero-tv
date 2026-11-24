"""AIRSPACE — every aircraft broadcasting ADS-B within 60 nautical miles, on a radar scope."""
import math

import pygame
import requests

from tvkit import text, theme
from tvkit.module import Module

from . import data

RANGE_NM = 60
CX, CY, R = 404, 368, 318
RX0, RX1 = 790, 1250
SPOT_S = 15
SWEEP_S = 6                     # one turn of the scope every six seconds
# approach-control scope: green phosphor on black glass, paper flight strips on the right
GLASS, SCOPE, RING = (2, 9, 5), (3, 20, 11), (18, 74, 40)
PHOS, DIMP, FAINT = (110, 255, 160), (46, 150, 86), (28, 96, 56)
STRIP, STRIP_EDGE, INKC, EMERG = (232, 222, 188), (176, 160, 120), (34, 32, 26), (255, 70, 56)
STRIP_H, STRIPS = 96, 5


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
    fps = 15
    footer_color = DIMP

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

    # -- the scope -------------------------------------------------------------------
    def draw_frame(self, surf):
        surf.fill(GLASS)
        pygame.draw.circle(surf, SCOPE, (CX, CY), R)
        for k in range(1, 5):
            r = R * k // 4
            pygame.draw.circle(surf, RING, (CX, CY), r, 1)
            text.draw(surf, f"{RANGE_NM * k // 4}", (CX + 5, CY - r + 3), "scope", 14, FAINT)
        for ang in range(0, 360, 10):                    # bearing ticks around the rim
            a = math.radians(ang)
            k = 0.94 if ang % 30 else 0.9
            pygame.draw.line(surf, RING, (CX + k * R * math.sin(a), CY - k * R * math.cos(a)),
                             (CX + R * math.sin(a), CY - R * math.cos(a)), 1)
        for ang in range(0, 360, 30):
            a = math.radians(ang)
            text.draw(surf, f"{ang:03d}", (CX + (R + 22) * math.sin(a), CY - (R + 16) * math.cos(a)), "scope", 14,
                      DIMP, anchor="center")
        pygame.draw.circle(surf, RING, (CX, CY), R, 2)
        text.draw(surf, "Approach", (30, 24), "scope-700", 24, PHOS)
        text.draw(surf, self.place.name if self.place else "", (30, 54), "scope", 16, DIMP, max_w=220)

    def draw_static(self, surf):
        pygame.draw.circle(surf, PHOS, (CX, CY), 3)
        if not self.place:
            text.draw(surf, "No place set", (RX0, 60), "scope-700", 44, PHOS)
            text.draw(surf, "Add a [place] with lat and lon to ~/.config/pizero-tv/config.toml.", (RX0, 130),
                      "scope", 18, DIMP, max_w=RX1 - RX0)
            return
        ac = self.src.value
        if ac is None:
            msg = {"offline": "adsb.lol isn't answering. Aircraft appear when it does.",
                   "waiting": "Listening for aircraft."}.get(self.src.status, "")
            text.draw(surf, "No returns", (RX0, 40), "scope-700", 44, PHOS)
            for i, line in enumerate(text.wrap(msg, "scope", 18, RX1 - RX0)):
                text.draw(surf, line, (RX0, 110 + i * 26), "scope", 18, DIMP)
            self._returns = []
            return
        self._blips(surf, ac)
        self._rail(surf, ac)

    def _blips(self, surf, ac):
        spot = self._spot(ac)
        taken, self._returns = [], []
        order = ([spot] if spot else []) + [a for a in ac if a is not spot and not a.on_ground]
        for a in ac:
            x, y = self._xy(a)
            self._returns.append((x, y, math.radians(a.bearing), a))
            if a.on_ground:
                pygame.draw.circle(surf, FAINT, (int(x), int(y)), 2)
        for a in reversed(order):
            x, y = self._xy(a)
            col = EMERG if a.emergency else (PHOS if a is spot else DIMP)
            if a.track is not None and a.speed:
                L = 6 + a.speed / 30
                t = math.radians(a.track)
                pygame.draw.line(surf, col, (x, y), (x + L * math.sin(t), y - L * math.cos(t)), 1)
            pygame.draw.circle(surf, col, (int(x), int(y)), 3)
        for a in order:                                  # ATC data blocks: callsign, altitude and speed
            x, y = self._xy(a)
            box = pygame.Rect(x + 14, y - 30, 86, 34)
            if a.dist_nm > RANGE_NM * 0.9 or any(box.colliderect(t) for t in taken):
                continue
            taken.append(box)
            col = EMERG if a.emergency else (PHOS if a is spot else DIMP)
            pygame.draw.line(surf, col, (x + 3, y - 3), (x + 12, y - 12), 1)          # leader line
            text.draw(surf, a.callsign, (x + 14, y - 30), "scope-700", 14, col, max_w=86)
            fl = "GND" if a.on_ground else f"{a.alt // 100:03d}"
            text.draw(surf, f"{fl} {int(a.speed or 0) // 10:02d}", (x + 14, y - 15), "scope", 14, col, max_w=86)

    def _spot(self, ac):
        near = [a for a in ac if not a.on_ground][:5] or ac[:5]
        return near[self.spot_i % len(near)] if near else None

    def _rail(self, surf, ac):
        airborne = [a for a in ac if not a.on_ground]
        text.draw(surf, f"{len(airborne)} aircraft", (RX0, 22), "scope-700", 40, PHOS)
        text.draw(surf, f"airborne within {RANGE_NM} nautical miles", (RX0, 72), "scope", 16, DIMP)
        y = 108
        emerg = [a for a in ac if a.emergency]
        if emerg:
            e = emerg[0]
            pygame.draw.rect(surf, EMERG, (RX0, y, RX1 - RX0, 34))
            text.draw(surf, f"{e.callsign} squawking {e.squawk}: {e.emergency}", (RX0 + 10, y + 17), "scope-700",
                      16, INKC, anchor="midleft", max_w=RX1 - RX0 - 20)
            y += 44
        spot = self._spot(ac)
        for a in airborne[:STRIPS]:                       # paper flight progress strips, nearest first
            if y + STRIP_H > 680:
                break
            self._strip(surf, pygame.Rect(RX0, y, RX1 - RX0, STRIP_H - 10), a, a is spot)
            y += STRIP_H
        if not airborne:
            text.draw(surf, "Quiet skies: nothing airborne in range.", (RX0, y + 10), "scope", 18, DIMP)

    def _strip(self, surf, r, a, hot):
        pygame.draw.rect(surf, STRIP, r)
        pygame.draw.rect(surf, EMERG if a.emergency else (PHOS if hot else STRIP_EDGE), r, 3 if hot else 1)
        pygame.draw.line(surf, STRIP_EDGE, (r.left + 150, r.top + 6), (r.left + 150, r.bottom - 6), 1)
        pygame.draw.line(surf, STRIP_EDGE, (r.left + 300, r.top + 6), (r.left + 300, r.bottom - 6), 1)
        text.draw(surf, a.callsign, (r.left + 12, r.top + 8), "scope-700", 24, INKC, max_w=132)
        text.draw(surf, a.type or "type ?", (r.left + 12, r.top + 42), "scope", 15, INKC, max_w=132)
        text.draw(surf, a.reg or "", (r.left + 12, r.top + 62), "scope", 13, STRIP_EDGE, max_w=132)
        trend = "" if not a.rate or abs(a.rate) < 300 else (" climbing" if a.rate > 0 else " descending")
        text.draw(surf, _alt(a), (r.left + 162, r.top + 8), "scope-700", 20, INKC, max_w=132)
        text.draw(surf, trend.strip() or "level", (r.left + 162, r.top + 36), "scope", 15, INKC, max_w=132)
        text.draw(surf, f"{a.speed:.0f} kt" if a.speed else "", (r.left + 162, r.top + 58), "scope", 15, INKC)
        who = data.airline(a.callsign) or data.type_name(a.type) or "Unidentified"
        text.draw(surf, who, (r.left + 312, r.top + 8), "scope", 15, INKC, max_w=r.width - 322)
        point = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][round(a.bearing / 45) % 8]
        text.draw(surf, f"{a.dist_nm:.0f} nm {point}", (r.left + 312, r.top + 34), "scope-700", 16,
                  INKC, max_w=r.width - 322)
        if a.track is not None:
            text.draw(surf, f"heading {a.track:03.0f}", (r.left + 312, r.top + 58), "scope", 15, INKC)

    def draw_live(self, surf, t):
        # the sweep, and returns that flare as it passes over them and fade until the next turn
        ang = (t % SWEEP_S) / SWEEP_S * 2 * math.pi
        for k in range(16):
            a = ang - k * 0.035
            col = theme.mix(SCOPE, PHOS, 0.55 * (1 - k / 16))
            pygame.draw.line(surf, col, (CX, CY), (CX + R * math.sin(a), CY - R * math.cos(a)), 2)
        for x, y, b, ac in getattr(self, "_returns", []):
            since = (ang - b) % (2 * math.pi) / (2 * math.pi)      # 0 just swept, 1 about to be swept
            if since < 0.35:
                k = 1 - since / 0.35
                pygame.draw.circle(surf, theme.mix(SCOPE, EMERG if ac.emergency else PHOS, k), (int(x), int(y)),
                                   3 + int(3 * k))
        return True


MODULE = Airspace
