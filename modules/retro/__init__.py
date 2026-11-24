"""OUTRUN — three retro screens: a synthwave road, Conway's Game of Life, and a nixie-tube clock."""
import math, random, time

import numpy as np
import pygame

from tvkit import text, theme
from tvkit.module import Module

MODES = ["outrun", "life", "nixie"]
MODE_S = 60
X0, W, H = 150, 1130, 720
HORIZON = 430
PINK, CYAN, SUNSET = (255, 46, 136), (64, 224, 255), (255, 170, 60)
NIXIE, NIXIE_OFF = (255, 140, 40), (52, 30, 22)


class Life:
    def __init__(self, w, h, seed=None):
        self.rng = np.random.default_rng(seed)
        self.grid = np.zeros((h, w), dtype=np.uint8)
        self._seen = []
        self.seed()

    def seed(self):
        self.grid[:] = (self.rng.random(self.grid.shape) < 0.22).astype(np.uint8)
        self._seen = []

    def step(self):
        g = self.grid
        n = sum(np.roll(np.roll(g, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy, dx) != (0, 0))
        self.grid = ((n == 3) | ((g == 1) & (n == 2))).astype(np.uint8)
        h = hash(self.grid.tobytes())
        self._seen = (self._seen + [h])[-12:]
        if not self.grid.any() or self._seen.count(h) > 3:      # extinct or stuck in a loop: start over
            self.seed()


class Retro(Module):
    name, title, key = "retro", "OUTRUN", PINK
    blurb = "Synthwave road, Game of Life and a nixie clock"
    aliases = ("outrun", "synthwave", "arcade")
    order = 120
    fps = 10

    def __init__(self):
        super().__init__()
        self.mode_i = 0

    @property
    def mode(self):
        return MODES[self.mode_i]

    def next_mode(self):
        self.mode_i = (self.mode_i + 1) % len(MODES)
        self.dirty = True

    def start(self, ctx):
        super().start(ctx)
        self.life = Life(141, 90)
        self._life_t, self._life_img = 0.0, None
        self._mode_t = None
        self._stars = [(random.randint(0, W), random.randint(0, HORIZON - 60), random.random()) for _ in range(90)]

    def update(self, now):
        changed = super().update(now)
        if self._mode_t is None:
            self._mode_t = now
        elif now - self._mode_t >= MODE_S:
            self._mode_t = now
            self.next_mode()
            changed = True
        return changed

    def on_key(self, event):
        if event.key in (pygame.K_SPACE, pygame.K_RIGHT):
            self.next_mode()

    # -- static backdrops -------------------------------------------------------------
    def draw_static(self, surf):
        if self.mode == "outrun":
            self._outrun_static(surf)
        elif self.mode == "nixie":
            surf.fill((14, 10, 10), (X0 + 2, 0, W, H))

    def _outrun_static(self, surf):
        for y in range(HORIZON):                       # night sky to magenta haze
            k = y / HORIZON
            pygame.draw.line(surf, theme.mix((10, 6, 28), (90, 10, 70), k ** 2), (X0 + 2, y), (X0 + W, y))
        for x, y, b in self._stars:
            surf.set_at((X0 + x, y), theme.mix((10, 6, 28), (255, 255, 255), 0.3 + 0.7 * b))
        cx, cy, r = X0 + W // 2, HORIZON - 40, 170
        sun = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
        for y in range(2 * r):
            half = int(math.sqrt(max(0, r * r - (y - r) ** 2)))
            band = y > r * 0.9 and (y // 14) % 2 == 1      # the classic stripes across the lower half
            if half and not band:
                pygame.draw.line(sun, theme.mix(SUNSET, PINK, y / (2 * r)), (r - half, y), (r + half, y))
        surf.blit(sun, (cx - r, cy - r))
        rng = random.Random(7)
        for layer, col in ((0, (40, 12, 60)), (1, (24, 8, 40))):
            pts, x = [(X0 + 2, HORIZON)], X0 + 2
            while x < X0 + W:
                x += rng.randint(40, 110)
                pts.append((min(x, X0 + W), HORIZON - rng.randint(20 + layer * 10, 120 - layer * 40)))
            pts.append((X0 + W, HORIZON))
            pygame.draw.polygon(surf, col, pts)
        surf.fill((14, 4, 26), (X0 + 2, HORIZON, W, H - HORIZON))
        vx = X0 + W // 2
        for i in range(-16, 17):
            pygame.draw.line(surf, PINK, (vx + i * 12, HORIZON), (vx + i * 150, H), 1)
        pygame.draw.line(surf, CYAN, (X0 + 2, HORIZON), (X0 + W, HORIZON), 2)

    # -- animation -----------------------------------------------------------------------
    def draw_live(self, surf, t):
        if self.mode == "outrun":
            phase = (t * 0.6) % 1.0
            for i in range(14):
                z = (i + phase) / 14
                y = HORIZON + (H - HORIZON) * z ** 2.2
                pygame.draw.line(surf, PINK, (X0 + 2, y), (X0 + W, y), 1 if z < 0.5 else 2)
        elif self.mode == "life":
            if t - self._life_t > 0.15 or self._life_img is None:
                self.life.step()
                self._life_t = t
                img = np.zeros((*self.life.grid.T.shape, 3), dtype=np.uint8)
                img[:] = theme.GROUND
                img[self.life.grid.T == 1] = theme.SEAGLASS
                self._life_img = pygame.transform.scale(pygame.surfarray.make_surface(img), (141 * 8, 90 * 8))
            surf.blit(self._life_img, (X0 + 2 + (W - 141 * 8) // 2, 0))
        else:
            self._nixie(surf)
        return True

    def _nixie(self, surf):
        now = time.localtime()
        s = time.strftime("%H:%M:%S", now)
        size = 230
        f = text.font("display-600", size)
        w = f.size("88:88:88")[0]
        x, y = X0 + (W - w) // 2, 200
        for ch in s:
            cell = f.size("8" if ch.isdigit() else ":")[0]
            if ch.isdigit():
                surf.blit(text.render("8", "display-600", size, NIXIE_OFF), (x, y))
            dx = (cell - f.size(ch)[0]) // 2           # centre each lit digit over its unlit 8
            surf.blit(text.render(ch, "display-600", size, NIXIE), (x + dx, y))
            x += cell
        text.draw(surf, time.strftime("%A %-d %B %Y", now), (X0 + W // 2, 520), "sans", 26, (150, 100, 70),
                  anchor="midtop")


MODULE = Retro
