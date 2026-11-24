"""THREATS — who is attacking the internet right now, as seen by the SANS Internet Storm Center."""
import math

import pygame
import requests

from tvkit import fx, text, theme, world
from tvkit.module import Module

from . import data

UA = {"User-Agent": "Mozilla/5.0 pizero-tv (hobby display)"}
ISC = "https://isc.sans.edu/api"
# war room on an old CRT: amber phosphor on black, a lit threat ladder, a gridded world
INK, AMBER, DIM, GRID = (8, 6, 3), (255, 176, 46), (150, 98, 24), (64, 44, 12)
RED, WHITE = (255, 54, 40), (255, 236, 200)
MAP = (366, 104, 884, world.height_for(884))
LADDER = [("red", "Severe", RED), ("orange", "High", (255, 120, 30)), ("yellow", "Elevated", (255, 214, 50)),
          ("green", "Normal", (90, 230, 120))]
LEVEL_TEXT = {"green": "Normal activity", "yellow": "A new threat is spreading",
              "orange": "A major threat is causing disruption", "red": "Widespread disruption"}
LADDER_Y, RUNG_H = 104, 58


def _get(url):
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_attackers():
    attacks = _get(f"{ISC}/sources/attacks/40?json")
    geo = requests.post("http://ip-api.com/batch?fields=status,query,countryCode,country,lat,lon,isp",
                        json=[a["ip"] for a in attacks], timeout=20).json()
    return {"attacks": attacks, "geo": geo}


def _short(n):
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.0f}k" if n >= 1e4 else f"{n:,}"


class Threats(Module):
    name, title, key = "threatmap", "THREATS", theme.KEYS["threatmap"]
    blurb = "The war room: who is attacking the internet right now"
    aliases = ("threats", "cyberthreats", "botnets")
    order = 40
    fps = 12
    footer_color = DIM

    def start(self, ctx):
        super().start(ctx)
        self.level = self.source("infocon", lambda: _get(f"{ISC}/infocon?json"), 900, parse=data.parse_infocon)
        self.ports = self.source("ports", lambda: _get(f"{ISC}/topports/records/12?json"), 1800,
                                 parse=data.parse_ports)
        self.attackers = self.source("attackers", fetch_attackers, 1800, parse=data.parse_attackers)
        self.feodo = self.source("feodo", lambda: _get("https://feodotracker.abuse.ch/downloads/ipblocklist.json"),
                                 3600, parse=data.parse_feodo)
        self.proj = world.Projection(MAP)
        self._blink = None
        self._map = None
        self._dots = []

    # -- the war room ----------------------------------------------------------------
    def draw_frame(self, surf):
        surf.fill(INK)
        text.draw(surf, "Threat watch", (30, 22), "stencil", 46, AMBER)
        text.draw(surf, "Internet Storm Center feed", (34, 82), "term", 18, DIM)
        if self._map is None:
            self._map = world.render(MAP, (34, 24, 8), (110, 72, 18))
        x, y, w, h = MAP
        for lon in range(-180, 181, 30):                 # the plotting grid under the map
            px = self.proj.to_px(lon, 0)[0]
            pygame.draw.line(surf, GRID, (px, y), (px, y + h), 1)
        for lat in range(-60, 91, 30):
            py = self.proj.to_px(0, lat)[1]
            if y <= py <= y + h:
                pygame.draw.line(surf, GRID, (x, py), (x + w, py), 1)
        surf.blit(self._map, (x, y))
        pygame.draw.rect(surf, DIM, (x - 1, y - 1, w + 2, h + 2), 1)
        for cx, cy in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):      # corner ticks
            pygame.draw.line(surf, AMBER, (cx - 8, cy), (cx + 8, cy), 2)
            pygame.draw.line(surf, AMBER, (cx, cy - 8), (cx, cy + 8), 2)

    def draw_static(self, surf):
        from datetime import datetime, timezone
        text.draw(surf, datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%MZ"), (1250, 30), "term", 26, AMBER,
                  anchor="topright")
        self._ladder(surf)
        self._ports(surf)
        self._world(surf)
        self._notes(surf)
        fx.scanlines(surf, strength=34, every=3)

    def draw_live(self, surf, t):
        # the lit rung blinks like a panel lamp; a scan bar sweeps the map; the biggest dots pulse
        if self._blink is not None and int(t * 1.6) % 2:
            r, label, col = self._blink
            pygame.draw.rect(surf, theme.mix(INK, col, 0.55), r)
            text.draw(surf, label, (r.left + 16, r.centery), "stencil", 34, INK, anchor="midleft")
        x, y, w, h = MAP
        sx = x + int((t * 90) % w)
        pygame.draw.line(surf, theme.mix(INK, AMBER, 0.55), (sx, y), (sx, y + h), 1)
        for p, r in self._dots[-5:]:
            k = (math.sin(t * 3 + p[0] * 0.01) + 1) / 2
            pygame.draw.circle(surf, RED, p, int(r + 4 + 7 * k), 1)
        return True

    def _ladder(self, surf):
        lvl = self.level.value
        self._blink = None
        for i, (name, label, col) in enumerate(LADDER):
            r = pygame.Rect(30, LADDER_Y + i * (RUNG_H + 8), 306, RUNG_H)
            if name == lvl:
                pygame.draw.rect(surf, col, r)
                text.draw(surf, label, (r.left + 16, r.centery), "stencil", 34, INK, anchor="midleft")
                self._blink = (r, label, col)
            else:
                pygame.draw.rect(surf, theme.mix(INK, col, 0.35), r, 2)
                text.draw(surf, label, (r.left + 16, r.centery), "stencil", 34, theme.mix(INK, col, 0.45),
                          anchor="midleft")
        y = LADDER_Y + 4 * (RUNG_H + 8) + 6
        if lvl is None:
            msg = {"offline": "The Internet Storm Center isn't answering.",
                   "waiting": "Asking the Internet Storm Center."}.get(self.level.status, "")
        else:
            msg = LEVEL_TEXT[lvl] + ", says the SANS Internet Storm Center."
        for i, line in enumerate(text.wrap(msg, "term", 18, 306)[:3]):
            text.draw(surf, line, (30, y + i * 22), "term", 18, AMBER)

    def _ports(self, surf):
        x, y = 30, 452
        ports = self.ports.value
        text.draw(surf, "Most probed ports", (x, y), "stencil", 24, AMBER)
        if not ports:
            text.draw(surf, "No port data yet.", (x, y + 36), "term", 18, DIM)
            return
        top = ports[0].records
        for i, p in enumerate(ports[:6]):
            ry = y + 36 + i * 30
            text.draw(surf, f"{p.port:>5}", (x, ry), "term", 22, WHITE)
            text.draw(surf, (p.service or "unassigned")[:14], (x + 76, ry), "term", 20, DIM, max_w=150)
            bw = max(2, int(76 * p.records / top))
            pygame.draw.rect(surf, GRID, (x + 230, ry + 8, 76, 10))
            pygame.draw.rect(surf, AMBER, (x + 230, ry + 8, bw, 10))

    def _world(self, surf):
        att = self.attackers.value
        self._dots = []
        x, y, w, h = MAP
        if not att:
            msg = {"offline": "Attacker data isn't available right now.",
                   "waiting": "Locating today's most active attackers."}.get(self.attackers.status, "")
            text.draw(surf, msg, (x + 20, y + h - 40), "term", 20, AMBER)
            return
        top = max(a.reports for a in att) or 1
        for a in sorted(att, key=lambda a: a.reports):
            if a.lat is None:
                continue
            p = self.proj.to_px(a.lon, a.lat)
            r = 3 + int(12 * math.sqrt(a.reports / top))
            pygame.draw.circle(surf, RED, p, r)
            pygame.draw.line(surf, RED, (p[0] - r - 5, p[1]), (p[0] + r + 5, p[1]), 1)     # crosshair
            pygame.draw.line(surf, RED, (p[0], p[1] - r - 5), (p[0], p[1] + r + 5), 1)
            self._dots.append((p, r))

    def _notes(self, surf):
        x, y = MAP[0], MAP[1] + MAP[3] + 22
        att = self.attackers.value
        if att:
            text.draw(surf, "Where the 40 busiest attackers are", (x, y), "stencil", 24, AMBER)
            for i, (cc, name, ips, rep) in enumerate(data.by_country(att)[:4]):
                text.draw(surf, f"{name}: {ips} IPs, {_short(rep)} reports",
                          (x + (i % 2) * 440, y + 36 + (i // 2) * 28), "term", 20, WHITE, max_w=430)
            a = att[0]
            where = f"{a.country}, {a.isp}" if a.country else "unknown location"
            text.draw(surf, f"Busiest: {a.ip} ({where}), {_short(a.reports)} reports from {a.targets} sensors",
                      (x, y + 102), "term", 18, AMBER, max_w=MAP[2])
        c2 = self.feodo.value
        if c2 is not None:
            online = [c for c in c2 if c.online]
            fams = sorted({c.malware for c in online})
            s = f"Feodo Tracker: {len(c2)} botnet command servers listed, {len(online)} online"
            s += f" ({', '.join(fams)})" if fams else ""
            text.draw(surf, s, (x, y + 128), "term", 18, DIM, max_w=MAP[2])


MODULE = Threats
