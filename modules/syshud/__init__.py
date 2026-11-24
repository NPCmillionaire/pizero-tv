"""SYSTEM — this Pi and any other machine running the stats agent, on a BIOS setup screen."""
import shutil, time

import pygame
import requests

from tvkit import text, theme
from tvkit.module import Module

from . import data

MB, GB = 1024 * 1024, 1024 ** 3
# the BIOS setup screen: blue field, grey frame, white labels, yellow values, cyan bars
BLUE, GREY, WHITE, YELLOW = (0, 0, 168), (170, 170, 170), (255, 255, 255), (255, 255, 85)
CYAN, RED, DARK = (85, 255, 255), (255, 85, 85), (0, 0, 110)
TOP, BOTTOM = 92, 500                  # machine panels
HINT = "Show other machines: run tools/install_agent.sh on them, then add [[system.hosts]] to config.toml"


def _gb(b):
    return f"{b / GB:,.1f} GB" if b >= GB else f"{b / MB:,.0f} MB"


class System(Module):
    name, title, key = "syshud", "SYSTEM", theme.KEYS["syshud"]
    blurb = "System setup: this Pi and your other machines"
    aliases = ("system", "hud")
    order = 80
    footer_color = GREY

    def start(self, ctx):
        super().start(ctx)
        self.hist = data.History(60)
        self._prev, self.rx = None, None
        self.stats = self.source("stats", data.snapshot, 2, parse=self._stats, cache=False)
        self.procs = self.source("procs", data.processes, 6, cache=False)
        self.thr = None
        if shutil.which("vcgencmd") or ctx.fakes is not None:      # Raspberry Pi only
            self.thr = self.source("throttle", data.throttled, 30, parse=lambda p: data.parse_throttled(p["raw"]),
                                   cache=False)
        self.remote, self._rprev, self._rrate = [], {}, {}
        for name, url in data.hosts(ctx.config.raw):
            src = self.source(f"host_{name}", lambda u=url: requests.get(u + "/stats", timeout=5).json(), 5,
                              parse=lambda p, n=name: self._remote(n, p), cache=False)
            self.remote.append((name, url, src))

    def _stats(self, s):
        cores = s["cores"]
        total = sum(cores) / len(cores) if cores else 0.0
        self.hist.add(total)
        self.rx = data.rates(self._prev, s)
        self._prev = s
        return dict(s, total=total)

    def _remote(self, name, p):
        prev = self._rprev.get(name)
        if prev and p.get("net_rx") is not None and prev.get("net_rx") is not None and p["time"] > prev["time"]:
            dt = p["time"] - prev["time"]
            self._rrate[name] = ((p["net_rx"] - prev["net_rx"]) / dt, (p["net_tx"] - prev["net_tx"]) / dt)
        self._rprev[name] = p
        return p

    def status(self):
        """The footer reports this Pi's own readings; each other machine shows its state in its panel."""
        st = self.stats.status
        return st, (self.stats.age_s if st == "stale" else None)

    def panels(self):
        local = self.stats.value
        out = [((local or {}).get("host", "this pi"), "local", self.stats)]
        out += [(n, "remote", src) for n, _, src in self.remote]
        return out

    # -- the setup screen ------------------------------------------------------------
    def draw_frame(self, surf):
        surf.fill(BLUE)
        text.draw(surf, "pizero-tv System Setup Utility", (640, 14), "vga", 34, WHITE, anchor="midtop")
        text.draw(surf, "Copyright (C) legitbiz.research", (640, 46), "vga", 24, GREY, anchor="midtop")
        pygame.draw.rect(surf, GREY, (14, 80, 1252, 600), 2)
        pygame.draw.rect(surf, GREY, (20, 86, 1240, 588), 2)
        pygame.draw.line(surf, GREY, (20, 630), (1260, 630), 2)
        text.draw(surf, "tv up / tv down: change channel     tv 0: guide     tv stop: standby", (40, 652), "vga",
                  24, GREY, anchor="midleft")

    def draw_static(self, surf):
        ps = self.panels()
        n = max(len(ps), 2)
        w = (1240 - 20 - (n - 1) * 12) // n
        for i, (name, kind, src) in enumerate(ps):
            r = pygame.Rect(30 + i * (w + 12), TOP + 6, w, BOTTOM - TOP)
            self._panel(surf, r, name, kind, src)
        if len(ps) == 1:
            r = pygame.Rect(30 + w + 12, TOP + 6, w, BOTTOM - TOP)
            pygame.draw.rect(surf, DARK, r)
            for j, line in enumerate(text.wrap(HINT, "vga", 26, w - 40)):
                text.draw(surf, line, (r.left + 20, r.top + 30 + j * 30), "vga", 26, GREY)
        self._procs(surf)

    def _panel(self, surf, r, name, kind, src):
        pygame.draw.rect(surf, GREY, (r.left, r.top, r.width, 34))
        text.draw(surf, name, (r.left + 12, r.top + 17), "vga", 30, BLUE, anchor="midleft", max_w=r.width - 140)
        st = src.status if kind == "remote" else None
        if st:
            text.draw(surf, {"live": "online", "stale": "lagging", "offline": "no answer",
                             "waiting": "asking"}[st], (r.right - 12, r.top + 17), "vga", 26,
                      BLUE if st == "live" else (170, 0, 0), anchor="midright")
        s = src.value
        x, y, w = r.left + 12, r.top + 46, r.width - 24
        if s is None:
            msg = ("Reading the system." if kind == "local" else
                   "No stats agent answering. Run tools/install_agent.sh on this machine.")
            for j, line in enumerate(text.wrap(msg, "vga", 26, w)):
                text.draw(surf, line, (x, y + j * 28), "vga", 26, GREY)
            return
        if kind == "local":
            rows = self._local_rows(s)
        else:
            rows = self._remote_rows(name, s)
        line_h = min(36, (r.bottom - y) // max(1, len(rows)))
        for label, value, bar in rows:
            text.draw(surf, label, (x, y), "vga", 26, WHITE)
            text.draw(surf, value, (x + 112, y), "vga", 26, YELLOW, max_w=w - 112)
            if bar is not None:
                self._blocks(surf, (x + 112, y + 26, w - 112, 6), bar)
            y += line_h

    def _blocks(self, surf, rect, frac):
        x, y, w, h = rect
        n = max(1, w // 10)
        lit = round(n * max(0.0, min(1.0, frac)))
        for k in range(n):
            col = (RED if frac >= 0.9 else CYAN) if k < lit else DARK
            pygame.draw.rect(surf, col, (x + k * 10, y, 8, h))

    def _local_rows(self, s):
        rows = [("CPU", f"{s['total']:.0f}%  {len(s['cores'])} cores", s["total"] / 100),
                ("Cores", "  ".join(f"{c:.0f}" for c in s["cores"]), None)]
        la = s.get("load") or []
        if la:
            rows.append(("Load", f"{la[0]:.2f} {la[1]:.2f} {la[2]:.2f}", None))
        rows.append(("Memory", f"{_gb(s['mem_used'])} / {_gb(s['mem_total'])}",
                     s["mem_used"] / s["mem_total"] if s["mem_total"] else 0))
        if s["swap_total"]:
            rows.append(("Swap", f"{_gb(s['swap_used'])} / {_gb(s['swap_total'])}", s["swap_used"] / s["swap_total"]))
        if s.get("temp") is not None:
            rows.append(("Temp", f"{s['temp']:.1f} C", None))
        thr = self.thr.value if self.thr else None
        if thr is not None:
            rows.append(("Power", "UNDERVOLT NOW" if thr["now"] else ("was throttled" if thr["since_boot"] else "OK"),
                         None))
        rows.append(("Uptime", data.uptime_text(time.time() - s["boot"]), None))
        if self.rx and self.rx[0] is not None:
            rows.append(("Net", f"down {data.human_rate(self.rx[0])}  up {data.human_rate(self.rx[1])}", None))
        return rows

    def _remote_rows(self, name, s):
        rows = [("System", f"{s.get('os', '?')} {s.get('os_release') or ''}".strip(), None)]
        if s.get("model"):
            rows.append(("Chip", s["model"].replace("(R)", "").replace("(TM)", "").replace(" CPU", ""), None))
        cpu = s.get("cpu")
        rows.append(("CPU", (f"{cpu:.0f}%" if cpu is not None else "?") + f"  {s.get('cores', '?')} cores",
                     (cpu or 0) / 100))
        la = s.get("load") or []
        if la:
            rows.append(("Load", f"{la[0]:.2f} {la[1]:.2f} {la[2]:.2f}", None))
        if s.get("mem_total"):
            rows.append(("Memory", f"{_gb(s['mem_used'])} / {_gb(s['mem_total'])}", s["mem_used"] / s["mem_total"]))
        if s.get("disk_total"):
            rows.append(("Disk", f"{_gb(s['disk_used'])} / {_gb(s['disk_total'])}", s["disk_used"] / s["disk_total"]))
        if s.get("temp") is not None:
            rows.append(("Temp", f"{s['temp']:.1f} C", None))
        if s.get("boot"):
            rows.append(("Uptime", data.uptime_text(s["time"] - s["boot"]), None))
        rate = self._rrate.get(name)
        if rate:
            rows.append(("Net", f"down {data.human_rate(rate[0])}  up {data.human_rate(rate[1])}", None))
        return rows

    def _procs(self, surf):
        y = BOTTOM + 16
        name = (self.stats.value or {}).get("host", "this pi")
        text.draw(surf, f"Busiest on {name}", (40, y), "vga", 26, WHITE)
        for i, p in enumerate((self.procs.value or [])[:6]):
            col, row = i // 3, i % 3
            x, ry = 340 + col * 460, y + row * 30
            text.draw(surf, p["name"], (x, ry), "vga", 26, GREY, max_w=250)
            text.draw(surf, f"{p['cpu']:>3.0f}%  {p['rss'] / MB:>4,.0f} MB", (x + 420, ry), "vga", 26, YELLOW,
                      anchor="topright")

    def draw_live(self, surf, t):
        # the BIOS cursor blinks on the bottom line
        if int(t * 2) % 2 == 0:
            pygame.draw.rect(surf, WHITE, (1230, 640, 14, 24))
        return False


MODULE = System
