#!/usr/bin/env python3
"""SF DISPATCH — live SFPD dispatched calls on a street map of San Francisco.

Data: data.sf.gov "Law Enforcement Dispatched Calls for Service: Real-Time"
(gnap-fj3t), refreshed ~every 10 min. Keys: Q/Esc quit, Space highlight next call.
"""
import json, math, os, sys, threading, time
from collections import Counter
from datetime import datetime, timedelta

os.environ.setdefault("SDL_VIDEODRIVER", "wayland")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame  # noqa: E402

import ui  # noqa: E402
from feed import LA, Feed, now_la, stats  # noqa: E402
from geo import Projector  # noqa: E402
from replay import Replayer  # noqa: E402

W, H, FPS = 1280, 720, 30
POLL_S = 60
MAP = (20, 72, 860, 520)
QUEUE = (900, 72, 360, 520)
BOTTOM_Y, BOTTOM_H = 604, 92
FADE_MIN = 60          # pins fade to the floor over this many minutes
RIPPLE_S = 1.5
LAYER_REFRESH_S = 10   # aged-pin layer re-render interval
QUEUE_SKIP = {"Passing Call"}  # officer drive-bys: counted and mapped, but not queue-worthy
HERE = os.path.dirname(os.path.abspath(__file__))


class Fetcher(threading.Thread):
    """Polls the feed in the background; hands batches + stats to the UI thread."""

    def __init__(self):
        super().__init__(daemon=True)
        self.feed = Feed()
        self.lock = threading.Lock()
        self.batches = []      # list of (calls, initial)
        self.stats = None
        self.status, self.age = "CONNECTING", None
        self.polls = 0

    def run(self):
        while True:
            new = self.feed.poll()
            st = stats(self.feed.calls) if self.feed.calls else None
            with self.lock:
                if new:
                    self.batches.append((new, self.polls == 0 or not self.stats))
                if st:
                    self.stats = st
                self.status, self.age = self.feed.status, self.feed.data_age
            self.polls += 1
            time.sleep(POLL_S)

    def take(self):
        with self.lock:
            b, self.batches = self.batches, []
            return b, self.stats, self.status, self.age


def load_basemap():
    with open(os.path.join(HERE, "basemap.json")) as fh:
        return json.load(fh)


def project_line(proj, pts):
    out = [proj.to_px(x, y) for x, y in pts]
    return [p for p in out if p]


def render_basemap(proj, bm):
    surf = pygame.Surface(MAP[2:]).convert()
    surf.fill((9, 13, 21))
    ox, oy = MAP[0], MAP[1]
    hood_polys = {}
    for hd in bm["hoods"]:
        polys = []
        for ring in hd["rings"]:
            pts = [(x - ox, y - oy) for x, y in project_line(proj, ring)]
            if len(pts) >= 3:
                polys.append(pts)
                pygame.draw.polygon(surf, (14, 20, 31), pts)
        hood_polys[hd["name"]] = polys
    for cls, color, width in (("secondary", (26, 34, 48), 1), ("primary", (38, 50, 70), 1),
                              ("motorway", (58, 74, 100), 2)):
        for line in bm["roads"][cls]:
            pts = [(x - ox, y - oy) for x, y in project_line(proj, line)]
            if len(pts) >= 2:
                pygame.draw.lines(surf, color, False, pts, width)
    for polys in hood_polys.values():
        for pts in polys:
            pygame.draw.lines(surf, (32, 44, 62), True, pts, 1)
    return surf, hood_polys


def render_hood_glow(hood_polys, calls):
    """Faint fill per neighborhood, proportional to its 24h call count."""
    layer = pygame.Surface(MAP[2:], pygame.SRCALPHA)
    counts = Counter(c.hood for c in calls if c.hood in hood_polys)
    if not counts:
        return layer
    top = max(counts.values())
    for name, n in counts.items():
        a = int(4 + 30 * (n / top) ** 0.7)
        for pts in hood_polys[name]:
            pygame.draw.polygon(layer, (*ui.ACCENT, a), pts)
    return layer


def age_min(call, now):
    return max(0.0, (now - call.received).total_seconds() / 60)


def pin_alpha(call, now):
    return int(max(40, 255 - (255 - 40) * min(1.0, age_min(call, now) / FADE_MIN)))


def render_pins(proj, calls, now):
    """Static layer of all revealed pins, faded by age (redrawn every LAYER_REFRESH_S)."""
    layer = pygame.Surface(MAP[2:], pygame.SRCALPHA)
    ox, oy = MAP[0], MAP[1]
    for c in sorted(calls, key=lambda c: c.received):
        p = proj.to_px(c.lon, c.lat) if c.lon is not None else None
        if not p:
            continue
        old = age_min(c, now) > FADE_MIN
        r = 1 if old else {"A": 4, "B": 3}.get(c.priority, 2)
        col = ui.PRIORITY.get(c.priority, ui.MUTED)
        pygame.draw.circle(layer, (*col, pin_alpha(c, now)), (p[0] - ox, p[1] - oy), r)
    return layer


def fmt_dur(td):
    s = int(td.total_seconds())
    return f"{s // 60}m{s % 60:02d}s" if s >= 60 else f"{s}s"


def draw_header(screen, st, status, age, now):
    pygame.draw.rect(screen, (10, 14, 22), (0, 0, W, 56))
    pygame.draw.line(screen, ui.EDGE, (0, 56), (W, 56))
    ui.text(screen, "SF DISPATCH", (24, 14), 24, ui.TEXT, bold=True)
    ui.text(screen, "SFPD COMPUTER-AIDED DISPATCH · LIVE CALLS FOR SERVICE", (210, 22), 12, ui.MUTED)
    right = W - 24
    clock = now.strftime("%H:%M PT")
    r = ui.text(screen, clock, (right, 28), 18, ui.TEXT, mono=True, anchor="midright")
    right = r.left - 24
    if status == "LIVE":
        col, label = ui.GREEN, f"LIVE · data {int(age.total_seconds() // 60)}m old"
    elif status == "STALE":
        col = ui.AMBER
        label = f"STALE · {int(age.total_seconds() // 60)}m old" if age else "STALE · no data"
    elif status == "OFFLINE":
        col, label = ui.RED, "OFFLINE · retrying"
    else:
        col, label = ui.MUTED, "CONNECTING…"
    f = ui.font(12, bold=True)
    bw = f.size(label)[0] + 30
    badge = pygame.Rect(right - bw, 16, bw, 24)
    pygame.draw.rect(screen, (*col, 255), badge, 1, border_radius=12)
    pygame.draw.circle(screen, col, (badge.left + 12, badge.centery), 4)
    ui.text(screen, label, (badge.left + 22, badge.centery), 12, col, bold=True, anchor="midleft")
    right = badge.left - 20
    if st:
        ui.text(screen, f"{st.total:,} calls · 24h", (right, 28), 14, ui.TEXT, anchor="midright")


def draw_queue(screen, recent, highlight, now):
    ui.panel(screen, QUEUE, "LATEST CALLS")
    x, y, w, h = QUEUE
    row_h = 40
    top = y + 34
    if not recent:
        ui.text(screen, "Waiting for calls…", (x + 14, top + 8), 14, ui.MUTED)
    for i, c in enumerate(recent[: (h - 40) // row_h]):
        ry = top + i * row_h
        if i == highlight:
            pygame.draw.rect(screen, (22, 30, 44), (x + 6, ry - 2, w - 12, row_h - 2), border_radius=4)
        col = ui.PRIORITY.get(c.priority, ui.MUTED)
        chip = pygame.Rect(x + 14, ry + 3, 18, 16)
        pygame.draw.rect(screen, col, chip, border_radius=3)
        ui.text(screen, c.priority, chip.center, 11, ui.BG, bold=True, anchor="center")
        ui.text(screen, c.received.strftime("%H:%M"), (x + 40, ry + 3), 13, ui.MUTED, mono=True)
        ui.text(screen, c.type, (x + 88, ry + 2), 14, ui.TEXT, max_w=w - 102)
        where = c.hood if c.hood != "Unknown" else "location withheld"
        if c.place:
            where += " · " + c.place
        ui.text(screen, where, (x + 40, ry + 21), 12, ui.MUTED, max_w=w - 54)


def draw_bars(screen, rect, title, rows, color):
    ui.panel(screen, rect, title)
    x, y, w, _ = rect
    if not rows:
        ui.text(screen, "—", (x + 14, y + 34), 14, ui.MUTED)
        return
    top = rows[0][1]
    label_w = int(w * 0.45)
    for i, (name, n) in enumerate(rows[:3]):
        ry = y + 32 + i * 18
        ui.text(screen, name, (x + 14, ry), 12, ui.TEXT, max_w=label_w - 8)
        bx, bw = x + 14 + label_w, w - label_w - 70
        pygame.draw.rect(screen, (24, 32, 46), (bx, ry + 4, bw, 8), border_radius=4)
        pygame.draw.rect(screen, color, (bx, ry + 4, max(4, int(bw * n / top)), 8), border_radius=4)
        ui.text(screen, f"{n:,}", (x + w - 14, ry), 12, ui.MUTED, mono=True, anchor="topright")


def draw_dispatch(screen, rect, st):
    ui.panel(screen, rect, "MEDIAN TIME TO DISPATCH")
    x, y, w, _ = rect
    labels = {"A": "Priority A · emergency", "B": "Priority B · urgent", "C": "Priority C · routine"}
    for i, p in enumerate("ABC"):
        ry = y + 32 + i * 18
        pygame.draw.circle(screen, ui.PRIORITY[p], (x + 20, ry + 8), 4)
        ui.text(screen, labels[p], (x + 32, ry), 12, ui.TEXT, max_w=w - 120)
        v = st.median_dispatch.get(p) if st else None
        ui.text(screen, fmt_dur(v) if v else "—", (x + w - 14, ry), 12, ui.MUTED, mono=True,
                anchor="topright")


def draw_map_overlay(screen, proj, active, highlight_call, t, st):
    """Per-frame: arrival ripples, pulsing priority-A pins, highlight ring."""
    for c, t0 in active:
        p = proj.to_px(c.lon, c.lat) if c.lon is not None else None
        if not p:
            continue
        k = (t - t0) / RIPPLE_S
        if 0 <= k < 1:
            col = ui.PRIORITY.get(c.priority, ui.MUTED)
            r = int(4 + 22 * k)
            s = pygame.Surface((2 * r + 4, 2 * r + 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*col, int(220 * (1 - k))), (r + 2, r + 2), r, 2)
            screen.blit(s, (p[0] - r - 2, p[1] - r - 2))
    if highlight_call and highlight_call.lon is not None:
        p = proj.to_px(highlight_call.lon, highlight_call.lat)
        if p:
            r = 10 + 2 * math.sin(t * 4)
            pygame.draw.circle(screen, ui.TEXT, p, int(r), 1)
    x, y, w, h = MAP
    if st and st.unplotted:
        ui.text(screen, f"{st.unplotted:,} calls without a public location (sensitive or unmapped)",
                (x + 12, y + h - 22), 11, ui.DIM, max_w=w - 24)
    legend = [("A", "emergency"), ("B", "urgent"), ("C", "routine")]
    lx = x + 12
    for p, name in legend:
        pygame.draw.circle(screen, ui.PRIORITY[p], (lx + 4, y + 18), 4)
        r = ui.text(screen, f"{p} {name}", (lx + 12, y + 11), 11, ui.MUTED)
        lx = r.right + 16


def pulse_a(screen, proj, calls, now, t):
    for c in calls:
        if c.priority != "A" or c.lon is None or age_min(c, now) > FADE_MIN:
            continue
        p = proj.to_px(c.lon, c.lat)
        if p:
            k = (math.sin(t * 3 + hash(c.cad) % 7) + 1) / 2
            pygame.draw.circle(screen, (255, 120, 120), p, int(4 + 2 * k), 1)


def main():
    pygame.init()
    flags = pygame.SCALED | pygame.DOUBLEBUF
    if os.environ.get("SFD_WINDOWED") != "1":
        flags |= pygame.FULLSCREEN
    screen = pygame.display.set_mode((W, H), flags)
    pygame.display.set_caption("SF Dispatch")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    proj = Projector(MAP)
    base, hood_polys = render_basemap(proj, load_basemap())
    glow = render_hood_glow(hood_polys, [])
    pins = pygame.Surface(MAP[2:], pygame.SRCALPHA)
    last_layer = -1e9

    fetcher = Fetcher()
    fetcher.start()
    replayer = Replayer(window=POLL_S)
    shown = []          # revealed calls, oldest first
    active = []         # (call, reveal_t) for ripples
    st, status, age = None, "CONNECTING", None
    highlight = -1
    dirty = True
    snap = os.environ.get("SFD_SNAPSHOT")          # dev: save a frame and exit
    snap_after = float(os.environ.get("SFD_SNAPSHOT_AFTER", "8"))
    t_start = time.monotonic()

    while True:
        clock.tick(FPS)
        t = time.monotonic()
        now = now_la()
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key in (pygame.K_q, pygame.K_ESCAPE)):
                pygame.quit()
                return
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_SPACE, pygame.K_RIGHT):
                highlight = (highlight + 1) % 12

        batches, new_st, status, age = fetcher.take()
        for b, initial in batches:
            replayer.add(b, t, initial=initial)
        if new_st is not st and new_st is not None:
            st = new_st
            glow = render_hood_glow(hood_polys, fetcher.feed.calls[:])
        for c in replayer.due(t):
            shown.append(c)
            active.append((c, t))
            dirty = True
        active = [(c, t0) for c, t0 in active if t - t0 < RIPPLE_S]
        cutoff = now - timedelta(hours=24)
        if shown and shown[0].received < cutoff:
            shown = [c for c in shown if c.received >= cutoff]

        if dirty or t - last_layer > LAYER_REFRESH_S:
            pins = render_pins(proj, shown, now)
            last_layer, dirty = t, False

        screen.fill(ui.BG)
        screen.blit(base, MAP[:2])
        screen.blit(glow, MAP[:2])
        screen.blit(pins, MAP[:2])
        pygame.draw.rect(screen, ui.EDGE, MAP, 1, border_radius=2)
        recent = sorted((c for c in shown if c.type not in QUEUE_SKIP),
                        key=lambda c: c.received, reverse=True)[:12]
        hl = recent[highlight] if 0 <= highlight < len(recent) else None
        pulse_a(screen, proj, shown[-300:], now, t)
        draw_map_overlay(screen, proj, active, hl, t, st)
        draw_header(screen, st, status, age, now)
        draw_queue(screen, recent, highlight, now)
        gap, pw = 20, (W - 40 - 40) // 3
        draw_bars(screen, (20, BOTTOM_Y, pw, BOTTOM_H), "CALL TYPES · 24H",
                  st.top_types if st else [], ui.ACCENT)
        draw_bars(screen, (20 + pw + gap, BOTTOM_Y, pw, BOTTOM_H), "BUSIEST NEIGHBORHOODS · 24H",
                  st.top_hoods if st else [], ui.AMBER)
        draw_dispatch(screen, (20 + 2 * (pw + gap), BOTTOM_Y, pw, BOTTOM_H), st)
        ui.text(screen, "legitbiz.research", (W - 20, H - 6), 11, ui.DIM, anchor="bottomright")
        ui.text(screen, "data.sf.gov · gnap-fj3t", (20, H - 6), 11, ui.DIM, anchor="bottomleft")
        pygame.display.flip()
        if snap and t - t_start > snap_after:
            pygame.image.save(screen, snap)
            pygame.quit()
            return


if __name__ == "__main__":
    main()
