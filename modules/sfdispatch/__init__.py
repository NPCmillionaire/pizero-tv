"""DISPATCH — live SFPD calls for service on a street map of San Francisco."""
import json, math, os, threading
from collections import Counter
from datetime import timedelta

import pygame

from tvkit import text, theme
from tvkit.module import Module

from .feed import Feed, _ts, now_la, requests_get_json, stats
from .geo import Projector
from .replay import Replayer

HERE = os.path.dirname(os.path.abspath(__file__))
MAP = (190, 36, 640, 560)
RX0, RX1 = 870, 1250
FADE_MIN = 60
RIPPLE_S = 1.5
QUEUE_SKIP = {"Passing Call"}      # officer drive-bys: counted and mapped, not listed
PRI = {"A": theme.CORAL, "B": theme.SODIUM, "C": theme.SEAGLASS, "?": theme.LICHEN}
PRI_WORD = {"A": "emergency", "B": "urgent", "C": "routine"}
LAND, HOOD_EDGE = (16, 41, 48), (24, 56, 64)
ROADS = (("secondary", (27, 58, 66), 1), ("primary", (38, 74, 82), 1), ("motorway", (62, 100, 104), 2))


def _fmt_dur(td):
    s = int(td.total_seconds())
    return f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"


class Dispatch(Module):
    name, title, key = "sfdispatch", "DISPATCH", theme.KEYS["sfdispatch"]
    blurb = "Live San Francisco police calls for service"
    aliases = ("dispatch", "sf")
    order = 90

    def start(self, ctx):
        super().start(ctx)
        self.clock = now_la
        if ctx.fakes is not None and ctx.fakes.get("sfpd"):
            last = max(r["received_datetime"] for r in ctx.fakes["sfpd"])
            frozen = _ts(last) + timedelta(minutes=10)
            self.clock = lambda: frozen
        self.feed = Feed(fetch=None, clock=self.clock)
        self.lock = threading.Lock()
        self.pending, self.initial = [], True
        self.replayer = Replayer(window=60, max_window=720)
        self.shown, self.active, self.highlight = [], [], -1
        self.proj = Projector(MAP)
        self._base = self._hoods = None
        self._last_fade = 0.0
        self.src = self.source("sfpd", lambda: requests_get_json(self.feed.next_url()), 60,
                               parse=self._ingest, cache=False)

    # data (runs on the Source thread) ------------------------------------------
    def _ingest(self, rows):
        new = self.feed.ingest(rows)
        with self.lock:
            if new:
                self.pending.append((new, self.initial))
                self.initial = False
        return len(self.feed.calls)

    def status(self):
        st, age = super().status()
        if st == "live" and self.feed.status == "STALE":
            return "stale", self.feed.data_age.total_seconds() if self.feed.data_age else None
        return st, age

    # host hooks -------------------------------------------------------------------
    def update(self, now):
        changed = super().update(now)
        with self.lock:
            batches, self.pending = self.pending, []
        for b, initial in batches:
            self.replayer.add(b, now, initial=initial)
        due = self.replayer.due(now)
        if due:
            self.shown.extend(due)
            fresh = [(c, now) for c in due] if len(due) < 50 else []   # no ripple storm at startup
            self.active.extend(fresh)
            changed = True
        cutoff = self.clock() - timedelta(hours=24)
        if self.shown and self.shown[0].received < cutoff:
            self.shown = [c for c in self.shown if c.received >= cutoff]
        if now - self._last_fade > 10:          # pins fade with age
            self._last_fade, changed = now, True
        return changed

    def on_key(self, event):
        if event.key in (pygame.K_SPACE, pygame.K_RIGHT):
            self.highlight = (self.highlight + 1) % max(1, len(self._recent()))
            self.dirty = True

    def _recent(self):
        return sorted((c for c in self.shown if c.type not in QUEUE_SKIP),
                      key=lambda c: c.received, reverse=True)[:8]

    # drawing ----------------------------------------------------------------------
    def _basemap(self):
        if self._base is None:
            with open(os.path.join(HERE, "basemap.json")) as fh:
                bm = json.load(fh)
            surf = pygame.Surface(MAP[2:])
            surf.fill(theme.GROUND)
            ox, oy = MAP[0], MAP[1]
            hoods = {}
            for hd in bm["hoods"]:
                polys = []
                for ring in hd["rings"]:
                    pts = [(p[0] - ox, p[1] - oy) for p in map(lambda q: self.proj.to_px(*q), ring) if p]
                    if len(pts) >= 3:
                        polys.append(pts)
                        pygame.draw.polygon(surf, LAND, pts)
                hoods[hd["name"]] = polys
            for cls, col, w in ROADS:
                for line in bm["roads"][cls]:
                    pts = [(p[0] - ox, p[1] - oy) for p in map(lambda q: self.proj.to_px(*q), line) if p]
                    if len(pts) >= 2:
                        pygame.draw.lines(surf, col, False, pts, w)
            for polys in hoods.values():
                for pts in polys:
                    pygame.draw.lines(surf, HOOD_EDGE, True, pts, 1)
            self._base, self._hoods = surf, hoods
        return self._base

    def draw_static(self, surf):
        base = self._basemap().copy()
        now = self.clock()
        counts = Counter(c.hood for c in self.shown if c.hood in self._hoods)
        if counts:
            glow = pygame.Surface(MAP[2:], pygame.SRCALPHA)
            top = max(counts.values())
            for hood, n in counts.items():
                for pts in self._hoods[hood]:
                    pygame.draw.polygon(glow, (*self.key, int(3 + 20 * (n / top) ** 0.8)), pts)
            base.blit(glow, (0, 0))
        pins = pygame.Surface(MAP[2:], pygame.SRCALPHA)
        for c in self.shown:
            p = self.proj.to_px(c.lon, c.lat) if c.lon is not None else None
            if not p:
                continue
            age = (now - c.received).total_seconds() / 60
            a = int(max(46, 255 - 209 * min(1.0, age / FADE_MIN)))
            r = 1 if age > FADE_MIN else {"A": 4, "B": 3}.get(c.priority, 2)
            pygame.draw.circle(pins, (*PRI.get(c.priority, theme.LICHEN), a), (p[0] - MAP[0], p[1] - MAP[1]), r)
        base.blit(pins, (0, 0))
        surf.blit(base, MAP[:2])
        self._draw_rail(surf, now)
        self._draw_bottom(surf)

    def _draw_rail(self, surf, now):
        st = self.src.status
        hour = [c for c in self.shown if now - c.received <= timedelta(hours=1)]
        text.draw(surf, "Calls in the last hour", (RX0, 40), "sans", 20, theme.LICHEN)
        hero = str(len(hour)) if self.shown else "—"
        r = text.draw(surf, hero, (RX0 - 4, 62), "display", 150, theme.BONE)
        by = Counter(c.priority for c in hour)
        y = 72
        for p in "ABC":
            pygame.draw.circle(surf, PRI[p], (r.right + 26, y + 13), 5)
            text.draw(surf, f"{by.get(p, 0)} {PRI_WORD[p]}", (r.right + 38, y), "sans", 20, theme.BONE,
                      max_w=RX1 - r.right - 40)
            y += 34
        y = 252
        pygame.draw.line(surf, theme.TIDE, (RX0, y - 12), (RX1, y - 12), 1)
        recent = self._recent()
        if not recent:
            msg = {"offline": "data.sf.gov isn't answering. Nothing is shown rather than a guess.",
                   "waiting": "Waiting for the first calls from data.sf.gov."}.get(st, "No calls yet.")
            for i, line in enumerate(text.wrap(msg, "sans", 20, RX1 - RX0)):
                text.draw(surf, line, (RX0, y + 4 + i * 28), "sans", 20, theme.LICHEN)
        for i, c in enumerate(recent):
            ry = y + i * 42
            if i == self.highlight:
                pygame.draw.rect(surf, theme.TIDE, (RX0 - 10, ry - 4, RX1 - RX0 + 20, 40))
            pygame.draw.circle(surf, PRI.get(c.priority, theme.LICHEN), (RX0 + 5, ry + 11), 5)
            t = c.received.strftime("%H:%M")
            text.draw(surf, t, (RX0 + 18, ry + 1), "sans", 17, theme.LICHEN)
            text.draw(surf, c.type, (RX0 + 72, ry - 1), "sans-500", 20, theme.BONE, max_w=RX1 - RX0 - 72)
            where = c.hood if c.hood != "Unknown" else "Location withheld"
            if c.place and c.place.lower() != "not available":
                where += ", " + c.place
            text.draw(surf, where, (RX0 + 72, ry + 19), "sans", 16, theme.LICHEN, max_w=RX1 - RX0 - 72)

    def _draw_bottom(self, surf):
        s = stats(self.shown) if self.shown else None
        y = 612
        if s and s.top_hoods:
            busiest = ", ".join(f"{h} {n}" for h, n in s.top_hoods[:3])
            text.draw(surf, "Busiest today: " + busiest, (190, y), "sans", 20, theme.BONE, max_w=650)
        if s and s.top_types:
            common = ", ".join(f"{t.lower()} {n}" for t, n in s.top_types[:3])
            text.draw(surf, "Most common: " + common, (190, y + 30), "sans", 20, theme.LICHEN, max_w=650)
        if s and "A" in s.median_dispatch:
            text.draw(surf, f"Emergencies dispatched in a median {_fmt_dur(s.median_dispatch['A'])}",
                      (RX0, y), "sans", 20, theme.BONE, max_w=RX1 - RX0)
        if s and s.unplotted:
            text.draw(surf, f"{s.unplotted:,} of {s.total:,} calls have no public location",
                      (RX0, y + 30), "sans", 16, theme.LICHEN, max_w=RX1 - RX0)

    def draw_live(self, surf, t):
        self.active = [(c, t0) for c, t0 in self.active if t - t0 < RIPPLE_S]
        now = self.clock()
        for c in self.shown[-300:]:
            if c.priority != "A" or c.lon is None or (now - c.received).total_seconds() > FADE_MIN * 60:
                continue
            p = self.proj.to_px(c.lon, c.lat)
            if p:
                k = (math.sin(t * 3 + hash(c.cad) % 7) + 1) / 2
                pygame.draw.circle(surf, theme.CORAL, p, int(5 + 3 * k), 1)
        for c, t0 in self.active:
            p = self.proj.to_px(c.lon, c.lat) if c.lon is not None else None
            k = (t - t0) / RIPPLE_S
            if p and 0 <= k < 1:
                r = int(4 + 24 * k)
                ring = pygame.Surface((2 * r + 4, 2 * r + 4), pygame.SRCALPHA)
                pygame.draw.circle(ring, (*PRI.get(c.priority, theme.LICHEN), int(230 * (1 - k))),
                                   (r + 2, r + 2), r, 2)
                surf.blit(ring, (p[0] - r - 2, p[1] - r - 2))
        recent = self._recent()
        if 0 <= self.highlight < len(recent) and recent[self.highlight].lon is not None:
            p = self.proj.to_px(recent[self.highlight].lon, recent[self.highlight].lat)
            if p:
                pygame.draw.circle(surf, theme.BONE, p, int(11 + 2 * math.sin(t * 4)), 1)
        return bool(self.active)    # ripples need 24 FPS; A-call pulses are fine at the idle rate


MODULE = Dispatch
