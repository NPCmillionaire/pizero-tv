"""SYSTEM — the Pi itself: CPU, memory, temperature, network and what's running."""
import shutil, time

import pygame

from tvkit import text, theme
from tvkit.module import Module

from . import data

X0, RX0, RX1 = 190, 810, 1250
MB = 1024 * 1024


class System(Module):
    name, title, key = "syshud", "SYSTEM", theme.KEYS["syshud"]
    blurb = "This Pi: processor, memory, temperature and network"
    aliases = ("system", "hud")
    order = 80

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

    def _stats(self, s):
        cores = s["cores"]
        total = sum(cores) / len(cores) if cores else 0.0
        self.hist.add(total)
        self.rx = data.rates(self._prev, s)
        self._prev = s
        return dict(s, total=total)

    def draw_static(self, surf):
        s = self.stats.value
        if s is None:
            text.draw(surf, "Reading the system.", (X0, 60), "sans", 24, theme.LICHEN)
            return
        self._cpu(surf, s)
        self._right(surf, s)
        self._procs(surf)

    def _cpu(self, surf, s):
        text.draw(surf, f"{s['host']}, {len(s['cores'])} cores", (X0, 28), "sans-500", 22, theme.BONE)
        r = text.draw(surf, f"{s['total']:.0f}%", (X0 - 6, 50), "display", 200, theme.BONE)
        text.draw(surf, "of the processor busy", (X0, r.bottom - 10), "sans", 20, theme.LICHEN)
        # per-core columns beside the hero
        bx, by, bh = r.right + 40, 80, 170
        for i, c in enumerate(s["cores"]):
            x = bx + i * 34
            pygame.draw.rect(surf, theme.TIDE, (x, by, 22, bh))
            h = int(bh * c / 100)
            pygame.draw.rect(surf, self.key, (x, by + bh - h, 22, h))
            text.draw(surf, str(i), (x + 11, by + bh + 6), "sans", 14, theme.LICHEN, anchor="midtop")
        # last two minutes
        x, y, w, h = X0, 318, 570, 90
        vals = self.hist.values
        pygame.draw.line(surf, theme.TIDE, (x, y + h), (x + w, y + h), 1)
        if len(vals) > 1:
            step = w / (self.hist._d.maxlen - 1)
            off = self.hist._d.maxlen - len(vals)
            pts = [(x + (off + i) * step, y + h - v / 100 * h) for i, v in enumerate(vals)]
            pygame.draw.polygon(surf, theme.mix(theme.GROUND, self.key, 0.25), pts + [(pts[-1][0], y + h), (pts[0][0], y + h)])
            pygame.draw.lines(surf, self.key, False, pts, 2)
        text.draw(surf, "Last two minutes", (x, y + h + 8), "sans", 16, theme.LICHEN)
        la = s.get("load") or []
        if la:
            text.draw(surf, f"Load {la[0]:.2f}, {la[1]:.2f}, {la[2]:.2f}", (x + w, y + h + 8), "sans", 16,
                      theme.LICHEN, anchor="topright")

    def _bar(self, surf, y, label, used, total, warn=0.85):
        text.draw(surf, label, (RX0, y), "sans", 18, theme.LICHEN)
        frac = used / total if total else 0
        text.draw(surf, f"{used / MB:,.0f} of {total / MB:,.0f} MB", (RX1, y), "sans-500", 18, theme.BONE,
                  anchor="topright")
        pygame.draw.rect(surf, theme.TIDE, (RX0, y + 28, RX1 - RX0, 10))
        pygame.draw.rect(surf, theme.CORAL if frac >= warn else self.key, (RX0, y + 28, int((RX1 - RX0) * frac), 10))

    def _right(self, surf, s):
        self._bar(surf, 34, "Memory in use", s["mem_used"], s["mem_total"])
        if s["swap_total"]:
            self._bar(surf, 92, "Swap in use", s["swap_used"], s["swap_total"], warn=0.7)
        y = 160
        if s.get("temp") is not None:
            t = s["temp"]
            col = theme.CORAL if t >= 75 else theme.SODIUM if t >= 65 else theme.BONE
            r = text.draw(surf, f"{t:.1f}°C", (RX0 - 4, y), "display", 96, col)
            text.draw(surf, "chip temperature", (r.right + 14, y + 52), "sans", 18, theme.LICHEN)
        thr = self.thr.value if self.thr else None
        y = 274
        if thr is not None:
            if thr["now"]:
                msg, col = "Right now: " + ", ".join(thr["now"]), theme.CORAL
            elif thr["since_boot"]:
                msg, col = "Since boot: " + ", ".join(thr["since_boot"]), theme.SODIUM
            else:
                msg, col = "Power and temperature have been fine since boot", theme.SEAGLASS
            text.draw(surf, msg, (RX0, y), "sans-500", 18, col, max_w=RX1 - RX0)
        text.draw(surf, f"Up {data.uptime_text(time.time() - s['boot'])}", (RX0, y + 30), "sans", 18, theme.LICHEN)
        y = 350
        rx, tx = self.rx if self.rx else (None, None)
        text.draw(surf, "Network", (RX0, y), "sans", 18, theme.LICHEN)
        if rx is not None:
            text.draw(surf, f"Down {data.human_rate(rx)}", (RX0, y + 24), "display-600", 34, theme.BONE)
            text.draw(surf, f"Up {data.human_rate(tx)}", (RX0 + 230, y + 24), "display-600", 34, theme.BONE)

    def _procs(self, surf):
        y = 460
        pygame.draw.line(surf, theme.TIDE, (X0, y - 12), (RX1, y - 12), 1)
        text.draw(surf, "Busiest processes", (X0, y), "sans-500", 20, theme.BONE)
        text.draw(surf, "processor", (X0 + 560, y + 2), "sans", 16, theme.LICHEN, anchor="topright")
        text.draw(surf, "memory", (X0 + 700, y + 2), "sans", 16, theme.LICHEN, anchor="topright")
        for i, p in enumerate((self.procs.value or [])[:6]):
            ry = y + 34 + i * 32
            text.draw(surf, p["name"], (X0, ry), "sans", 20, theme.BONE, max_w=420)
            text.draw(surf, f"{p['cpu']:.0f}%", (X0 + 560, ry), "sans-500", 20, theme.BONE, anchor="topright")
            text.draw(surf, f"{p['rss'] / MB:,.0f} MB", (X0 + 700, ry), "sans", 20, theme.LICHEN, anchor="topright")


MODULE = System
