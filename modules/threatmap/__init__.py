"""THREATS — who is attacking the internet right now, as seen by the SANS Internet Storm Center."""
import math

import pygame
import requests

from tvkit import text, theme, world
from tvkit.module import Module

from . import data

UA = {"User-Agent": "Mozilla/5.0 pizero-tv (hobby display)"}
ISC = "https://isc.sans.edu/api"
X0 = 190
MAP = (190, 214, 1060, world.height_for(1060))
LEVEL_COLOR = {"green": theme.SEAGLASS, "yellow": (247, 201, 72), "orange": theme.SODIUM, "red": theme.CORAL}
LEVEL_TEXT = {"green": "Normal activity", "yellow": "Elevated: a new threat is spreading",
              "orange": "High: a major threat is causing disruption", "red": "Severe: widespread disruption"}


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
    blurb = "Who is attacking the internet right now"
    aliases = ("threats", "cyberthreats", "botnets")
    order = 40

    def start(self, ctx):
        super().start(ctx)
        self.level = self.source("infocon", lambda: _get(f"{ISC}/infocon?json"), 900, parse=data.parse_infocon)
        self.ports = self.source("ports", lambda: _get(f"{ISC}/topports/records/12?json"), 1800,
                                 parse=data.parse_ports)
        self.attackers = self.source("attackers", fetch_attackers, 1800, parse=data.parse_attackers)
        self.feodo = self.source("feodo", lambda: _get("https://feodotracker.abuse.ch/downloads/ipblocklist.json"),
                                 3600, parse=data.parse_feodo)
        self.proj = world.Projection(MAP)
        self._map = None
        self._dots = []

    def draw_static(self, surf):
        self._hero(surf)
        self._ports(surf)
        self._world(surf)
        self._notes(surf)

    def _hero(self, surf):
        lvl = self.level.value
        text.draw(surf, "Internet threat level", (X0, 30), "sans-500", 22, theme.BONE)
        if lvl is None:
            text.draw(surf, "—", (X0 - 4, 52), "display", 120, theme.TIDE)
            msg = {"offline": "The Internet Storm Center isn't answering.",
                   "waiting": "Asking the Internet Storm Center."}.get(self.level.status, "")
            text.draw(surf, msg, (X0, 176), "sans", 18, theme.LICHEN, max_w=520)
            return
        col = LEVEL_COLOR[lvl]
        text.draw(surf, lvl.capitalize(), (X0 - 4, 52), "display", 120, col)
        text.draw(surf, LEVEL_TEXT[lvl] + ", says the SANS Internet Storm Center.", (X0, 176), "sans", 18,
                  theme.LICHEN, max_w=540)

    def _ports(self, surf):
        x, y = 760, 30
        ports = self.ports.value
        text.draw(surf, "Most probed ports today", (x, y), "sans-500", 22, theme.BONE)
        if not ports:
            text.draw(surf, "No port data yet.", (x, y + 36), "sans", 18, theme.LICHEN)
            return
        top = ports[0].records
        for i, p in enumerate(ports[:8]):
            col_x = x + (i // 4) * 252
            ry = y + 38 + (i % 4) * 36
            text.draw(surf, str(p.port), (col_x + 78, ry), "display-600", 30, self.key, anchor="topright")
            text.draw(surf, p.service or "unassigned", (col_x + 90, ry + 4), "sans", 18, theme.BONE, max_w=108)
            bw = max(2, int(36 * p.records / top))
            pygame.draw.rect(surf, theme.TIDE, (col_x + 204, ry + 14, 36, 6))
            pygame.draw.rect(surf, self.key, (col_x + 204, ry + 14, bw, 6))

    def _world(self, surf):
        if self._map is None:
            self._map = world.render(MAP, (21, 52, 60), (28, 66, 74))
        surf.blit(self._map, MAP[:2])
        att = self.attackers.value
        self._dots = []
        if not att:
            msg = {"offline": "Attacker data isn't available right now.",
                   "waiting": "Locating today's most active attackers."}.get(self.attackers.status, "")
            text.draw(surf, msg, (MAP[0] + 20, MAP[1] + MAP[3] - 40), "sans", 18, theme.LICHEN)
            return
        top = max(a.reports for a in att) or 1
        for a in sorted(att, key=lambda a: a.reports):
            if a.lat is None:
                continue
            p = self.proj.to_px(a.lon, a.lat)
            r = 3 + int(14 * math.sqrt(a.reports / top))
            glow = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*self.key, 50), (r * 2, r * 2), r * 2)
            surf.blit(glow, (p[0] - r * 2, p[1] - r * 2))
            pygame.draw.circle(surf, self.key, p, r)
            self._dots.append((p, r))
        rows = data.by_country(att)[:4]
        lx, ly = MAP[0] + 16, MAP[1] + MAP[3] - 30 - 28 * len(rows)
        text.draw(surf, "Where the 40 busiest attackers are", (lx, ly - 30), "sans-500", 18, theme.BONE,
                  max_w=290)
        for i, (cc, name, ips, rep) in enumerate(rows):
            text.draw(surf, f"{name}: {ips} IPs, {_short(rep)} reports", (lx, ly + i * 28), "sans", 18,
                      theme.LICHEN, max_w=290)

    def _notes(self, surf):
        y = MAP[1] + MAP[3] + 18
        att = self.attackers.value
        if att:
            a = att[0]
            where = f"{a.country}, {a.isp}" if a.country else "unknown location"
            text.draw(surf, f"Busiest attacker today: {a.ip} ({where}), {_short(a.reports)} reports from "
                            f"{a.targets} sensors.", (X0, y), "sans", 18, theme.BONE, max_w=840)
        c2 = self.feodo.value
        if c2 is not None:
            online = [c for c in c2 if c.online]
            fams = sorted({c.malware for c in online})
            s = f"Feodo Tracker lists {len(c2)} botnet command servers; {len(online)} online"
            s += f" ({', '.join(fams)})." if fams else "."
            text.draw(surf, s, (X0, y + 28), "sans", 16, theme.LICHEN, max_w=840)

    def draw_live(self, surf, t):
        # a slow breathing ring on the five biggest dots
        for p, r in self._dots[-5:]:
            k = (math.sin(t * 2 + p[0] * 0.01) + 1) / 2
            pygame.draw.circle(surf, theme.mix(theme.GROUND, self.key, 0.8), p, int(r + 4 + 6 * k), 1)
        return False


MODULE = Threats
