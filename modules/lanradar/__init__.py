"""LAN — what's on the home network: a sonar of real devices, with newcomers flagged."""
import concurrent.futures as cf
import json, math, os, re, socket, subprocess, threading, time

import pygame

from tvkit import text, theme
from tvkit.module import Module

from . import data

CX, CY, R = 400, 380, 290
RX0, RX1 = 760, 1250
PING_S = 4                       # one sonar ping every four seconds
# submarine sonar: cyan on deep water, contacts that light as each ping passes them
DEEPSEA, WATER, RINGC = (0, 9, 16), (0, 24, 36), (0, 66, 86)
CYAN, CDIM, NEWC, WHITE = (70, 232, 255), (32, 132, 156), (255, 150, 40), (210, 250, 255)
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
    fps = 15
    footer_color = CDIM

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
            return NEWC
        return CDIM if d.vendor == "Private address" else CYAN

    def draw_frame(self, surf):
        surf.fill(DEEPSEA)
        pygame.draw.circle(surf, WATER, (CX, CY), R)
        for k in range(1, 4):                         # dashed range rings
            r = int(R * (0.15 + 0.25 * k))
            for a in range(0, 360, 6):
                a0, a1 = math.radians(a), math.radians(a + 3)
                pygame.draw.line(surf, RINGC, (CX + r * math.sin(a0), CY - r * math.cos(a0)),
                                 (CX + r * math.sin(a1), CY - r * math.cos(a1)), 1)
        pygame.draw.circle(surf, RINGC, (CX, CY), R, 2)
        pygame.draw.line(surf, RINGC, (CX - R, CY), (CX + R, CY), 1)
        pygame.draw.line(surf, RINGC, (CX, CY - R), (CX, CY + R), 1)
        text.draw(surf, "Sonar", (30, 24), "term", 34, CYAN)
        text.draw(surf, "home network", (30, 62), "term", 18, CDIM)
        text.draw(surf, "nearer the middle answers faster", (CX, CY + R + 12), "term", 16, CDIM, anchor="midtop")

    def draw_static(self, surf):
        pygame.draw.circle(surf, CYAN, (CX, CY), 4)
        devs = self.src.value
        self._contacts = []
        if devs is None:
            msg = {"offline": "Couldn't read the network neighbor table on this machine.",
                   "waiting": "Listening to the network."}.get(self.src.status, "")
            text.draw(surf, "No contacts", (RX0, 24), "term", 54, CYAN)
            for i, line in enumerate(text.wrap(msg, "term", 20, RX1 - RX0)):
                text.draw(surf, line, (RX0, 100 + i * 28), "term", 20, CDIM)
            return
        taken = []
        for d in devs:
            x, y = self._xy(d)
            col = self._color(d)
            dist = math.hypot(x - CX, y - CY)
            self._contacts.append((int(x), int(y), dist, col))
            if d.new:                                  # newcomers get a triangle, like an unknown contact
                pygame.draw.polygon(surf, col, [(x, y - 7), (x + 7, y + 5), (x - 7, y + 5)], 2)
            else:
                pygame.draw.circle(surf, theme.mix(WATER, col, 0.6), (int(x), int(y)), 4)
            box = pygame.Rect(x + 9, y - 9, 120, 20)
            if not any(box.colliderect(t) for t in taken):
                taken.append(box)
                text.draw(surf, d.label, (x + 10, y - 9), "term", 15, theme.mix(WATER, col, 0.8), max_w=118)
        self._rail(surf, devs)

    def _rail(self, surf, devs):
        live = [d for d in devs if d.state in ("REACHABLE", "DELAY", "PROBE") or d.rtt_ms is not None]
        text.draw(surf, f"{len(live)} contacts", (RX0, 22), "term", 54, CYAN)
        text.draw(surf, f"answering now, {len(devs)} seen recently", (RX0, 84), "term", 20, CDIM, max_w=RX1 - RX0)
        y = 120
        new = [d for d in devs if d.new]
        if new:
            text.draw(surf, f"New today: {', '.join(d.label for d in new[:3])}", (RX0, y), "term", 20, NEWC,
                      max_w=RX1 - RX0)
            y += 30
        if not self.subnet:
            text.draw(surf, "Set [lan] subnet in config.toml to sweep for quiet devices.", (RX0, y), "term", 16,
                      CDIM, max_w=RX1 - RX0)
            y += 26
        y += 8
        text.draw(surf, "contact", (RX0 + 18, y), "term", 16, CDIM)
        text.draw(surf, "address", (RX0 + 250, y), "term", 16, CDIM)
        text.draw(surf, "echo", (RX1, y), "term", 16, CDIM, anchor="topright")
        pygame.draw.line(surf, RINGC, (RX0, y + 24), (RX1, y + 24), 1)
        y += 34
        rows = sorted(devs, key=lambda d: (not d.new, d.rtt_ms is None, d.rtt_ms or 0))
        for d in rows:
            if y > 664:
                break
            col = self._color(d)
            pygame.draw.circle(surf, col, (RX0 + 5, y + 10), 4)
            text.draw(surf, d.label, (RX0 + 18, y), "term", 19, WHITE if not d.new else NEWC, max_w=224)
            text.draw(surf, d.ip, (RX0 + 250, y + 1), "term", 18, CDIM)
            rtt = f"{d.rtt_ms:.0f} ms" if d.rtt_ms is not None else "silent"
            text.draw(surf, rtt, (RX1, y + 1), "term", 18, CDIM, anchor="topright")
            y += 27

    def draw_live(self, surf, t):
        # a ping ring expands from the middle; each contact flares as the ring reaches it
        k = (t % PING_S) / PING_S
        r = int(k * R)
        if r > 2:
            pygame.draw.circle(surf, theme.mix(WATER, CYAN, 0.9 * (1 - k)), (CX, CY), r, 2)
        for x, y, dist, col in getattr(self, "_contacts", []):
            behind = r - dist
            if 0 <= behind < 60:
                f = 1 - behind / 60
                pygame.draw.circle(surf, theme.mix(WATER, col, f), (x, y), 4 + int(4 * f))
        return True


MODULE = Lan
