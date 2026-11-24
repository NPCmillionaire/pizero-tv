"""LAN — what's on the home network: a sonar of real devices, with newcomers flagged."""
import concurrent.futures as cf
import json, math, os, re, socket, subprocess, threading, time

import pygame

from tvkit import text, theme
from tvkit.module import Module

from . import data

CX, CY, R = 488, 376, 296
RX0, RX1 = 840, 1250
SWEEP_EVERY = 300
RTT = re.compile(r"time=([\d.]+) ms")


def _ping(ip):
    try:
        out = subprocess.run(["ping", "-c1", "-W1", ip], capture_output=True, text=True, timeout=3).stdout
    except Exception:
        return ip, None
    m = RTT.search(out)
    return ip, float(m.group(1)) if m else None


def _rdns(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return None


class Lan(Module):
    name, title, key = "lanradar", "LAN", theme.KEYS["lanradar"]
    blurb = "Every device on the home network, with newcomers flagged"
    aliases = ("lan", "sonar")
    order = 85

    def start(self, ctx):
        super().start(ctx)
        self.subnet = ctx.config.lan_subnet
        self.known_path = os.path.join(ctx.cache_dir, "known.json") if ctx.cache_dir else None
        self.known = self._load_known()
        self._names, self._rtt, self._last_sweep = {}, {}, 0.0
        self.lock = threading.Lock()
        self.src = self.source("lan", self._scan, 30, parse=self._parse, cache=False)

    # -- collection (Source thread, on the Pi) ------------------------------------
    def _load_known(self):
        try:
            return json.load(open(self.known_path)) if self.known_path else {}
        except Exception:
            return {}

    def _scan(self):
        now = time.time()
        with cf.ThreadPoolExecutor(32) as pool:
            if self.subnet and now - self._last_sweep > SWEEP_EVERY:
                self._rtt = {ip: rtt for ip, rtt in pool.map(_ping, data.hosts(self.subnet)) if rtt is not None}
                self._last_sweep = now
            raw = subprocess.run(["ip", "-j", "neigh"], capture_output=True, text=True, timeout=5).stdout
            rows = data.parse_ip_neigh(raw)
            todo = [r["ip"] for r in rows if r["ip"] not in self._names]
            for ip, name in zip(todo, pool.map(_rdns, todo)):
                self._names[ip] = name.split(".")[0] if name else None
        return [dict(r, name=self._names.get(r["ip"]), rtt_ms=self._rtt.get(r["ip"])) for r in rows]

    def _parse(self, rows):
        before = len(self.known)
        devs = data.parse_devices(rows, self.known)
        if self.known_path and len(self.known) != before:
            os.makedirs(os.path.dirname(self.known_path), exist_ok=True)
            json.dump(self.known, open(self.known_path, "w"))
        return devs

    # -- drawing --------------------------------------------------------------------
    def _xy(self, d):
        octet = int(d.ip.rsplit(".", 1)[1])
        ang = math.radians(octet / 256 * 360)
        if d.rtt_ms is None:
            f = 0.9
        else:
            f = 0.15 + 0.75 * min(1.0, math.log10(max(1.0, d.rtt_ms)) / math.log10(300))
        return CX + f * R * math.sin(ang), CY - f * R * math.cos(ang)

    def _color(self, d):
        if d.new:
            return theme.SODIUM
        return theme.LICHEN if d.vendor == "Private address" else self.key

    def draw_static(self, surf):
        pygame.draw.circle(surf, theme.DEEP, (CX, CY), R)
        for i, lbl in ((1, "fast"), (2, ""), (3, "slow")):
            pygame.draw.circle(surf, theme.TIDE, (CX, CY), int(R * (0.15 + 0.25 * i)), 1)
        pygame.draw.circle(surf, self.key, (CX, CY), 4)
        text.draw(surf, "Closer to the middle answers pings faster", (CX, CY + R + 14), "sans", 14, theme.LICHEN,
                  anchor="midtop")
        devs = self.src.value
        if devs is None:
            msg = {"offline": "Couldn't read the network neighbor table on this machine.",
                   "waiting": "Listening to the network."}.get(self.src.status, "")
            text.draw(surf, "—", (RX0, 24), "display", 150, theme.TIDE)
            for i, line in enumerate(text.wrap(msg, "sans", 20, RX1 - RX0)):
                text.draw(surf, line, (RX0, 200 + i * 28), "sans", 20, theme.LICHEN)
            return
        taken = []
        for d in devs:
            x, y = self._xy(d)
            col = self._color(d)
            pygame.draw.circle(surf, col, (int(x), int(y)), 6 if d.new else 5)
            box = pygame.Rect(x + 8, y - 9, 120, 20)
            if not any(box.colliderect(t) for t in taken):
                taken.append(box)
                text.draw(surf, d.label, (x + 10, y - 9), "sans", 14, col, max_w=118)
        self._rail(surf, devs)

    def _rail(self, surf, devs):
        live = [d for d in devs if d.state in ("REACHABLE", "DELAY", "PROBE") or d.rtt_ms is not None]
        r = text.draw(surf, str(len(live)), (RX0 - 4, 24), "display", 150, theme.BONE)
        text.draw(surf, f"devices answering now, {len(devs)} seen recently", (RX0, r.bottom - 8), "sans", 20,
                  theme.LICHEN, max_w=RX1 - RX0)
        y = r.bottom + 30
        new = [d for d in devs if d.new]
        if new:
            text.draw(surf, f"New today: {', '.join(d.label for d in new[:3])}", (RX0, y), "sans-500", 20,
                      theme.SODIUM, max_w=RX1 - RX0)
            y += 32
        if not self.subnet:
            text.draw(surf, "Set [lan] subnet in config.toml to sweep for quiet devices.", (RX0, y), "sans", 16,
                      theme.LICHEN, max_w=RX1 - RX0)
            y += 26
        pygame.draw.line(surf, theme.TIDE, (RX0, y + 4), (RX1, y + 4), 1)
        y += 18
        rows = sorted(devs, key=lambda d: (not d.new, d.rtt_ms is None, d.rtt_ms or 0))
        for d in rows:
            if y > 660:
                break
            col = self._color(d)
            pygame.draw.circle(surf, col, (RX0 + 5, y + 11), 4)
            text.draw(surf, d.label, (RX0 + 18, y), "sans-500", 18, theme.BONE, max_w=210)
            text.draw(surf, d.ip, (RX0 + 236, y + 1), "sans", 16, theme.LICHEN)
            rtt = f"{d.rtt_ms:.0f} ms" if d.rtt_ms is not None else ""
            text.draw(surf, rtt, (RX1, y + 1), "sans", 16, theme.LICHEN, anchor="topright")
            y += 28

    def draw_live(self, surf, t):
        ang = (t % 30) / 30 * 2 * math.pi
        for k in range(10):
            a = ang - k * 0.035
            pygame.draw.line(surf, theme.mix(theme.DEEP, self.key, 0.45 * (1 - k / 10)), (CX, CY),
                             (CX + R * math.sin(a), CY - R * math.cos(a)), 2)
        return False


MODULE = Lan
