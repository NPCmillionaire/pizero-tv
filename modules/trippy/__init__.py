"""TRIPPY — generative color fields, computed with numpy at low resolution and scaled up."""
import numpy as np
import pygame

from tvkit.module import Module

FW, FH, SCALE = 282, 180, 4                # 1128 × 720 on screen, right of the spine
X0 = 150
FIELDS = ["flow", "kaleido", "tunnel", "moire", "nebula", "lava"]
FIELD_S = 60
_x = np.linspace(-FW / 2, FW / 2, FW, dtype=np.float32)[:, None]
_y = np.linspace(-FH / 2, FH / 2, FH, dtype=np.float32)[None, :]
X, Y = np.broadcast_to(_x, (FW, FH)), np.broadcast_to(_y, (FW, FH))
R = np.sqrt(X * X + Y * Y).astype(np.float32)
A = np.arctan2(Y, X).astype(np.float32)
# a fixed "noise" basis for the nebula: a few random directional waves
_rng = np.random.default_rng(3)
_waves = [(_rng.uniform(-1, 1, 2).astype(np.float32), np.float32(_rng.uniform(0.02, 0.12)), np.float32(_rng.uniform(0, 6)))
          for _ in range(7)]


def _norm(v):
    lo, hi = float(v.min()), float(v.max())
    return ((v - lo) / ((hi - lo) or 1.0)).astype(np.float32)


def field(name, t):
    t = np.float32(t)
    if name == "flow":
        v = np.sin(X * 0.05 + t) + np.sin(Y * 0.07 + t * 1.3) + np.sin((X + Y) * 0.035 + t * 0.7) + np.sin(R * 0.05 - t)
    elif name == "kaleido":
        fold = np.abs(((A * 6 / np.pi) % 2) - 1)
        v = np.sin(R * 0.09 - t * 2 + fold * 4) + np.sin(fold * 9 + t)
    elif name == "tunnel":
        depth = 600 / (R + 8)
        v = np.sin(depth + t * 3) * np.sin(A * 6 + t * 0.8 + depth * 0.2)
    elif name == "moire":
        c1 = (np.sin(t * 0.5) * 60, np.cos(t * 0.4) * 40)
        c2 = (np.cos(t * 0.3) * 70, np.sin(t * 0.6) * 30)
        d1 = np.sqrt((X - c1[0]) ** 2 + (Y - c1[1]) ** 2)
        d2 = np.sqrt((X - c2[0]) ** 2 + (Y - c2[1]) ** 2)
        v = np.sin(d1 * 0.35) + np.sin(d2 * 0.35)
    elif name == "nebula":
        v = np.zeros((FW, FH), np.float32)
        for (dx, dy), k, ph in _waves:
            v += np.sin((X * dx + Y * dy) * k + ph + t * 0.4) / k ** 0.3
        v = v + 0.5 * np.sin(R * 0.04 - t * 0.5)
    elif name == "lava":
        v = np.zeros((FW, FH), np.float32)
        for i in range(5):
            bx = np.sin(t * (0.3 + i * 0.07) + i * 1.7) * FW * 0.38
            by = np.cos(t * (0.25 + i * 0.05) + i * 2.3) * FH * 0.38
            v += 900.0 / ((X - bx) ** 2 + (Y - by) ** 2 + 60)
        v = np.tanh(v * 0.6)
    else:
        raise KeyError(name)
    return _norm(v)


PALETTES = [
    [(8, 23, 27), (19, 72, 84), (111, 214, 197), (238, 230, 211), (255, 166, 48)],     # petrol to sodium
    [(18, 6, 34), (88, 40, 160), (168, 139, 255), (255, 90, 95), (255, 196, 120)],     # violet dusk
    [(4, 14, 30), (22, 70, 120), (127, 178, 255), (220, 236, 255), (111, 214, 197)],   # deep water
    [(30, 6, 10), (140, 20, 40), (255, 90, 95), (255, 166, 48), (247, 201, 72)],       # lava
]


def palette(t, name_i=0):
    """256-color gradient through one of PALETTES, rolling slowly with time."""
    stops = np.array(PALETTES[name_i % len(PALETTES)], np.float32)
    x = (np.linspace(0, 1, 256, dtype=np.float32) + np.float32(t * 0.015)) % 1.0
    tri = 1 - np.abs(2 * x - 1)                    # 0 → 1 → 0 so the roll never shows a seam
    pos = tri * (len(stops) - 1)
    i = np.clip(pos.astype(int), 0, len(stops) - 2)
    f = (pos - i)[:, None]
    return (stops[i] * (1 - f) + stops[i + 1] * f).astype(np.uint8)


class Trippy(Module):
    name, title, key = "trippy", "TRIPPY", (190, 120, 255)
    blurb = "Generative color fields"
    order = 130
    fps = 15

    def start(self, ctx):
        super().start(ctx)
        self.i, self._t0 = 0, None

    def on_key(self, event):
        if event.key in (pygame.K_SPACE, pygame.K_RIGHT):
            self.i = (self.i + 1) % len(FIELDS)

    def draw_live(self, surf, t):
        if self._t0 is None:
            self._t0 = t
        if t - self._t0 >= FIELD_S:
            self.i, self._t0 = (self.i + 1) % len(FIELDS), t
        idx = (field(FIELDS[self.i], t) * 255).astype(np.uint8)
        img = palette(t, self.i)[idx]
        small = pygame.surfarray.make_surface(img)
        surf.blit(pygame.transform.scale(small, (FW * SCALE, FH * SCALE)), (X0 + 2, 0))
        return True


MODULE = Trippy
