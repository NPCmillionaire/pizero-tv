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
# computer-aided dispatch terminal: black screen, mono type, an inverted status bar, a call log
SCREEN, TXT, DIMT, FAINT = (4, 5, 8), (222, 226, 232), (122, 130, 144), (44, 48, 56)
MAP = (24, 74, 600, 552)
RX0, RX1 = 650, 1256
FADE_MIN = 60
RIPPLE_S = 1.5
QUEUE_SKIP = {"Passing Call"}      # officer drive-bys: counted and mapped, not listed
PRI = {"A": (255, 64, 64), "B": (255, 200, 40), "C": (80, 200, 255), "?": DIMT}
PRI_WORD = {"A": "emergency", "B": "urgent", "C": "routine"}
LAND, HOOD_EDGE = (18, 20, 24), (40, 44, 52)
ROADS = (("secondary", (34, 37, 43), 1), ("primary", (52, 56, 64), 1), ("motorway", (86, 92, 102), 2))


def _fmt_dur(td):
    s = int(td.total_seconds())
    return f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"


class Dispatch(Module):
    name, title, key = "sfdispatch", "DISPATCH", theme.KEYS["sfdispatch"]
    blurb = "Live San Francisco police calls for service"
    aliases = ("dispatch", "sf")
    order = 72
    footer_color = DIMT

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
        self._recent_cache, self._pulses = [], []
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
        if changed:
            self._refresh_cache()
        return changed

    def on_key(self, event):
        if event.key in (pygame.K_SPACE, pygame.K_RIGHT):
            self.highlight = (self.highlight + 1) % max(1, len(self._recent()))
            self.dirty = True

    def _recent(self):
        return self._recent_cache

    def _refresh_cache(self):
        """Per-data-change work, so draw_live does nothing heavier than circles."""
        now = self.clock()
        self._recent_cache = sorted((c for c in self.shown if c.type not in QUEUE_SKIP),
                                    key=lambda c: c.received, reverse=True)[:8]
        self._pulses = []
        for c in self.shown[-300:]:
            if c.priority == "A" and c.lon is not None and (now - c.received).total_seconds() <= FADE_MIN * 60:
                p = self.proj.to_px(c.lon, c.lat)
                if p:
                    self._pulses.append((p, hash(c.cad) % 7))

    # drawing ----------------------------------------------------------------------
    def _basemap(self):
        if self._base is None:
            with open(os.path.join(HERE, "basemap.json")) as fh:
                bm = json.load(fh)
            surf = pygame.Surface(MAP[2:])
            surf.fill(SCREEN)
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
                    pygame.draw.polygon(glow, (255, 255, 255, int(3 + 18 * (n / top) ** 0.8)), pts)
            base.blit(glow, (0, 0))
        pins = pygame.Surface(MAP[2:], pygame.SRCALPHA)
        for c in self.shown:
            p = self.proj.to_px(c.lon, c.lat) if c.lon is not None else None
            if not p:
                continue
            age = (now - c.received).total_seconds() / 60
            a = int(max(46, 255 - 209 * min(1.0, age / FADE_MIN)))
            r = 1 if age > FADE_MIN else {"A": 4, "B": 3}.get(c.priority, 2)
            pygame.draw.circle(pins, (*PRI.get(c.priority, DIMT), a), (p[0] - MAP[0], p[1] - MAP[1]), r)
        base.blit(pins, (0, 0))
        surf.blit(base, MAP[:2])
        pygame.draw.rect(surf, FAINT, (MAP[0] - 1, MAP[1] - 1, MAP[2] + 2, MAP[3] + 2), 1)
        self._draw_rail(surf, now)
        self._draw_bottom(surf)

    def draw_frame(self, surf):
        surf.fill(SCREEN)
        pygame.draw.rect(surf, TXT, (0, 18, 1280, 38))

    def _draw_rail(self, surf, now):
        st = self.src.status
        hour = [c for c in self.shown if now - c.received <= timedelta(hours=1)]
        by = Counter(c.priority for c in hour)
        text.draw(surf, "SFPD calls for service", (24, 37), "mono-500", 22, SCREEN, anchor="midleft")
        bar = (f"last hour {len(hour)}   A {by.get('A', 0)}   B {by.get('B', 0)}   C {by.get('C', 0)}   "
               f"{now.strftime('%H:%M')}" if self.shown else now.strftime("%H:%M"))
        text.draw(surf, bar, (1256, 37), "mono-500", 22, SCREEN, anchor="midright")
        y = 74
        text.draw(surf, "time  pri  call and location", (RX0, y), "mono", 18, DIMT)
        y += 30
        pygame.draw.line(surf, FAINT, (RX0, y - 6), (RX1, y - 6), 1)
        recent = self._recent()
        self._cursor = (RX0, y)
        if not recent:
            msg = {"offline": "data.sf.gov isn't answering. Nothing is shown rather than a guess.",
                   "waiting": "Waiting for the first calls from data.sf.gov."}.get(st, "No calls yet.")
            for i, line in enumerate(text.wrap(msg, "mono", 20, RX1 - RX0)):
                text.draw(surf, line, (RX0, y + 4 + i * 28), "mono", 20, TXT)
            self._cursor = (RX0, y + 8 + 28 * len(text.wrap(msg, "mono", 20, RX1 - RX0)))
            return
        for i, c in enumerate(recent):
            ry = y + i * 58
            if i == self.highlight:
                pygame.draw.rect(surf, (28, 32, 40), (RX0 - 8, ry - 6, RX1 - RX0 + 16, 54))
            col = PRI.get(c.priority, DIMT)
            text.draw(surf, c.received.strftime("%H:%M"), (RX0, ry), "mono", 20, DIMT)
            text.draw(surf, c.priority, (RX0 + 78, ry), "mono-500", 20, col)
            text.draw(surf, c.type, (RX0 + 116, ry), "mono-500", 20, TXT, max_w=RX1 - RX0 - 116)
            where = c.hood if c.hood != "Unknown" else "location withheld"
            if c.place and c.place.lower() != "not available":
                where += " / " + c.place
            text.draw(surf, where, (RX0 + 116, ry + 24), "mono", 16, DIMT, max_w=RX1 - RX0 - 116)
            self._cursor = (RX0, ry + 58)

    def _draw_bottom(self, surf):
        s = stats(self.shown) if self.shown else None
        y = 640
        x = 24
        if s and s.top_hoods:
            busiest = ", ".join(f"{h} {n}" for h, n in s.top_hoods[:3])
            text.draw(surf, "busiest today: " + busiest, (x, y), "mono", 17, TXT, max_w=600)
        if s and s.top_types:
            common = ", ".join(f"{t.lower()} {n}" for t, n in s.top_types[:3])
            text.draw(surf, "most common: " + common, (x, y + 24), "mono", 17, DIMT, max_w=600)
        if s and "A" in s.median_dispatch:
            text.draw(surf, f"emergencies dispatched in a median {_fmt_dur(s.median_dispatch['A'])}",
                      (RX0, y), "mono", 17, TXT, max_w=RX1 - RX0)
        if s and s.unplotted:
            text.draw(surf, f"{s.unplotted:,} of {s.total:,} calls have no public location",
                      (RX0, y + 24), "mono", 17, DIMT, max_w=RX1 - RX0)

    def draw_live(self, surf, t):
        self.active = [(c, t0) for c, t0 in self.active if t - t0 < RIPPLE_S]
        for p, phase in self._pulses:
            k = (math.sin(t * 3 + phase) + 1) / 2
            pygame.draw.circle(surf, PRI["A"], p, int(5 + 3 * k), 1)
        for c, t0 in self.active:
            p = self.proj.to_px(c.lon, c.lat) if c.lon is not None else None
            k = (t - t0) / RIPPLE_S
            if p and 0 <= k < 1:
                r = int(4 + 24 * k)
                ring = pygame.Surface((2 * r + 4, 2 * r + 4), pygame.SRCALPHA)
                pygame.draw.circle(ring, (*PRI.get(c.priority, DIMT), int(230 * (1 - k))),
                                   (r + 2, r + 2), r, 2)
                surf.blit(ring, (p[0] - r - 2, p[1] - r - 2))
        recent = self._recent()
        if 0 <= self.highlight < len(recent) and recent[self.highlight].lon is not None:
            p = self.proj.to_px(recent[self.highlight].lon, recent[self.highlight].lat)
            if p:
                pygame.draw.circle(surf, TXT, p, int(11 + 2 * math.sin(t * 4)), 1)
        cur = getattr(self, "_cursor", None)        # the terminal's block cursor, blinking under the log
        if cur and int(t * 2) % 2 == 0 and cur[1] < 620:
            pygame.draw.rect(surf, TXT, (cur[0], cur[1], 12, 20))
        return bool(self.active)    # ripples need 24 FPS; the cursor and A-call pulses are fine at the idle rate


MODULE = Dispatch
