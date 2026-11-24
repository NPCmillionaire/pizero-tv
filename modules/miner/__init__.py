"""MINER — the XMRig rig on arch and its MoneroOcean wallet, on a power-plant control panel."""
import math, time

import pygame
import requests

from tvkit import fx, text, theme
from tvkit.module import Module

from . import data

MO = "https://api.moneroocean.stream"
# control-room panel: painted sea-green steel, black bezels, cream meter faces, red needles
PANEL_TOP, PANEL_BOTTOM = (120, 150, 134), (86, 112, 100)
PLATE, ENGRAVE, FACE, INK, NEEDLE = (20, 22, 22), (236, 236, 228), (240, 234, 214), (30, 30, 30), (210, 30, 30)
LAMP = {"ok": (70, 230, 110), "warn": (255, 176, 40), "alarm": (255, 50, 40), "off": (58, 64, 60)}
GAUGES = [((214, 250), "Rig hashrate"), ((640, 250), "Pool sees"), ((1066, 250), "CPU load")]
GR = 150


def _hs(v):
    return "—" if v is None else (f"{v / 1000:.2f} kH/s" if v >= 1000 else f"{v:.0f} H/s")


def _dur(s):
    d, s = divmod(int(s), 86400)
    h, s = divmod(s, 3600)
    return f"{d}d {h}h" if d else f"{h}h {s // 60}m"


class Miner(Module):
    name, title, key = "miner", "MINER", theme.SODIUM
    blurb = "The Monero rig on arch, on a power-plant control panel"
    aliases = ("xmrig", "xmr", "mining")
    order = 82
    fps = 6
    footer_color = (30, 40, 36)

    def start(self, ctx):
        super().start(ctx)
        m = ctx.config.raw.get("miner") if isinstance(ctx.config.raw.get("miner"), dict) else {}
        self.url, self.token, self.wallet_id = m.get("url"), m.get("token"), m.get("wallet")
        self.rig = self.wallet = self.price = None
        if self.url:
            hdr = {"Authorization": f"Bearer {self.token}"} if self.token else {}
            url = self.url.rstrip("/") + "/2/summary"
            self.rig = self.source("rig", lambda: requests.get(url, headers=hdr, timeout=8).json(), 10,
                                   parse=data.parse_summary, cache=False)
        if self.wallet_id:
            w = self.wallet_id

            def fetch_wallet():
                return {"stats": requests.get(f"{MO}/miner/{w}/stats", timeout=15).json(),
                        "chart": requests.get(f"{MO}/miner/{w}/chart/hashrate", timeout=15).json()[:120]}
            self.wallet = self.source("wallet", fetch_wallet, 300,
                                      parse=lambda p: data.parse_wallet(p["stats"], p["chart"]))
            self.price = self.source("price", lambda: requests.get(
                "https://api.coingecko.com/api/v3/simple/price", params={"ids": "monero", "vs_currencies": "usd"},
                timeout=15).json(), 900, parse=data.parse_price)

    # -- the panel -----------------------------------------------------------------------
    def draw_frame(self, surf):
        surf.blit(fx.gradient((theme.W, theme.H), PANEL_TOP, PANEL_BOTTOM), (0, 0))
        for x in range(0, 1280, 320):                       # panel seams and rivets
            pygame.draw.line(surf, theme.mix(PANEL_BOTTOM, (0, 0, 0), 0.25), (x, 0), (x, 720), 1)
        for x, y in ((14, 14), (1266, 14), (14, 706), (1266, 706)):
            pygame.draw.circle(surf, theme.mix(PANEL_BOTTOM, (0, 0, 0), 0.4), (x, y), 4)
        self._plate(surf, pygame.Rect(30, 22, 620, 52), "Monero rig", 34)
        for (c, label) in GAUGES:
            self._plate(surf, pygame.Rect(c[0] - 120, c[1] + GR + 20, 240, 34), label, 24)

    def _plate(self, surf, r, s, size):
        pygame.draw.rect(surf, PLATE, r, border_radius=4)
        pygame.draw.rect(surf, (70, 76, 72), r, 2, border_radius=4)
        text.draw(surf, s, r.center, "display-600", size, ENGRAVE, anchor="center", max_w=r.width - 20)

    def draw_static(self, surf):
        rig = self.rig.value if self.rig else None
        wal = self.wallet.value if self.wallet else None
        if not self.url:
            text.draw(surf, "Add a [miner] section to ~/.config/pizero-tv/config.toml: url, token and wallet.",
                      (680, 48), "sans-500", 18, ENGRAVE, anchor="midleft", max_w=570)
        elif rig is None:
            msg = {"offline": "The rig's API isn't answering.", "waiting": "Calling the rig."}.get(self.rig.status, "")
            text.draw(surf, msg, (680, 48), "sans-500", 20, PLATE, anchor="midleft", max_w=570)
        else:
            text.draw(surf, f"{rig.cpu}, {rig.threads} threads. XMRig {rig.version}. Up {_dur(rig.uptime_s)}.",
                      (680, 48), "sans-500", 18, PLATE, anchor="midleft", max_w=570)
        top = data.gauge_max(max((rig.h10 or 0) if rig else 0, (wal.hash if wal else 0), rig.highest or 0 if rig else 0))
        self._gauge(surf, GAUGES[0][0], rig.h10 if rig else None, top, _hs(rig.h10) if rig else "no signal",
                    f"60 s {_hs(rig.h60)}   15 m {_hs(rig.h15m)}" if rig else "")
        self._gauge(surf, GAUGES[1][0], wal.hash if wal else None, top, _hs(wal.hash) if wal else "no signal",
                    "MoneroOcean's view" if wal else "")
        la = rig.load[0] if rig and rig.load else None
        self._gauge(surf, GAUGES[2][0], la, 4.0, f"{la:.2f}" if la is not None else "no signal", "load average",
                    unit="")
        self._lamps(surf, rig, wal)
        self._counters(surf, rig, wal)

    def _gauge(self, surf, c, v, top, readout, sub, unit="H/s"):
        cx, cy = c
        pygame.draw.circle(surf, PLATE, c, GR + 12)
        pygame.draw.circle(surf, (90, 96, 92), c, GR + 12, 3)
        pygame.draw.circle(surf, FACE, c, GR)
        a0, a1 = math.radians(225), math.radians(-45)           # a 270° sweep, low at bottom left
        red_from = 0.9
        for k in range(51):
            f = k / 50
            a = a0 + (a1 - a0) * f
            long = k % 5 == 0
            r0 = GR - (22 if long else 12)
            col = NEEDLE if f >= red_from else INK
            pygame.draw.line(surf, col, (cx + r0 * math.cos(a), cy - r0 * math.sin(a)),
                             (cx + (GR - 6) * math.cos(a), cy - (GR - 6) * math.sin(a)), 3 if long else 1)
            if k % 10 == 0:
                val = top * f
                lbl = f"{val / 1000:g}k" if unit == "H/s" and val >= 1000 else f"{val:g}"
                text.draw(surf, lbl, (cx + (GR - 44) * math.cos(a), cy - (GR - 44) * math.sin(a)), "display-600", 22,
                          INK, anchor="center")
        text.draw(surf, unit, (cx, cy - 46), "display-400", 20, INK, anchor="center")
        win = pygame.Rect(cx - 86, cy + 44, 172, 40)
        pygame.draw.rect(surf, (12, 14, 12), win)
        text.draw(surf, readout, win.center, "mono-500", 22, (120, 255, 140), anchor="center", max_w=164)
        if sub:
            text.draw(surf, sub, (cx, cy + 96), "sans", 15, INK, anchor="center", max_w=200)
        if v is not None:
            f = max(0.0, min(1.04, v / top))
            a = a0 + (a1 - a0) * f
            tip = (cx + (GR - 18) * math.cos(a), cy - (GR - 18) * math.sin(a))
            tail = (cx - 20 * math.cos(a), cy + 20 * math.sin(a))
            pygame.draw.line(surf, NEEDLE, tail, tip, 5)
        pygame.draw.circle(surf, INK, c, 12)

    def _lamps(self, surf, rig, wal):
        self._lamp_rects = []
        items = data.lamps(rig, wal) if self.url else [("Not configured", "warn")]
        w, gap, y = 196, 10, 510
        x0 = (1280 - (len(items) * w + (len(items) - 1) * gap)) // 2
        for i, (label, state) in enumerate(items):
            r = pygame.Rect(x0 + i * (w + gap), y, w, 56)
            pygame.draw.rect(surf, PLATE, r.inflate(8, 8))
            pygame.draw.rect(surf, LAMP[state] if state != "off" else LAMP["off"], r)
            text.draw(surf, label, r.center, "display-600", 22, INK if state != "off" else (120, 128, 122),
                      anchor="center", max_w=w - 12)
            self._lamp_rects.append((r, label, state))

    def _counters(self, surf, rig, wal):
        price = self.price.value if self.price else None
        cells = []
        if wal:
            usd = f"  ${wal.due_xmr * price:,.2f}" if price else ""
            cells.append(("Owed by the pool", f"{wal.due_xmr:.6f} XMR{usd}"))
            cells.append(("Paid out so far", f"{wal.paid_xmr:.6f} XMR"))
        if rig:
            cells.append(("Shares accepted", f"{rig.accepted:,}" + (f"  rejected {rig.rejected}" if rig.rejected else "")))
        if price:
            cells.append(("Monero price", f"${price:,.2f}"))
        if not cells:
            return
        w = (1220 - (len(cells) - 1) * 12) // len(cells)
        for i, (label, val) in enumerate(cells):
            r = pygame.Rect(30 + i * (w + 12), 600, w, 84)
            pygame.draw.rect(surf, PLATE, r, border_radius=4)
            text.draw(surf, label, (r.left + 14, r.top + 10), "display-600", 20, (170, 176, 170), max_w=w - 28)
            text.draw(surf, val, (r.left + 14, r.bottom - 10), "mono-500", 24, ENGRAVE, anchor="bottomleft",
                      max_w=w - 28)

    def draw_live(self, surf, t):
        # alarm lamps flash; everything else is still, like a real panel on a quiet day
        moving = False
        for r, label, state in getattr(self, "_lamp_rects", []):
            if state == "alarm":
                moving = True
                if int(t * 2) % 2:
                    pygame.draw.rect(surf, theme.mix(LAMP["alarm"], (0, 0, 0), 0.6), r)
                    text.draw(surf, label, r.center, "display-600", 22, INK, anchor="center", max_w=r.width - 12)
        return moving


MODULE = Miner
