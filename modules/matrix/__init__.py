"""MATRIX — digital rain in real half-width katakana. Pure art: no data, no pretend hacking."""
import random
from dataclasses import dataclass

import pygame

from tvkit import text, theme
from tvkit.module import Module

GLYPHS = [chr(c) for c in range(0xFF66, 0xFF9E)] + list("0123456789Z:.=*+-<>")
PALETTES = [((0, 255, 120), (190, 255, 210)), (theme.SEAGLASS, (220, 255, 250)), (theme.CORAL, (255, 220, 220))]
X0, CELL = 150, 18


@dataclass
class Column:
    x: int
    y: float
    speed: float


class Rain:
    def __init__(self, w, h, cell=CELL, seed=None):
        self.w, self.h, self.cell = w, h, cell
        self.rng = random.Random(seed)
        self.columns = [Column(i * cell, self.rng.uniform(-h, h), self.rng.uniform(6, 16) * cell)
                        for i in range(w // cell)]

    def step(self, dt):
        """Advance every drop; return the cells whose glyph changes this step as (x, y, char)."""
        out = []
        for c in self.columns:
            before = int(c.y // self.cell)
            c.y += c.speed * dt
            for row in range(before + 1, int(c.y // self.cell) + 1):
                out.append((c.x, row * self.cell, self.rng.choice(GLYPHS)))
            if c.y > self.h + self.cell * self.rng.randint(4, 30):
                c.y, c.speed = -self.rng.uniform(0, self.h / 3), self.rng.uniform(6, 16) * self.cell
        return out


class Matrix(Module):
    name, title, key = "matrix", "MATRIX", (0, 255, 120)
    blurb = "Digital rain, in real katakana"
    order = 110
    fps = 20

    def start(self, ctx):
        super().start(ctx)
        self.rain = Rain(1280 - X0, 720)
        self.layer = pygame.Surface((1280 - X0, 720)).convert() if pygame.display.get_surface() else \
            pygame.Surface((1280 - X0, 720))
        self.layer.fill((0, 0, 0))
        self.fade = pygame.Surface(self.layer.get_size())
        self.fade.fill((10, 10, 10))
        self.palette = 0
        self._glyphs = {}
        self._last = None

    def _glyph(self, ch, col):
        k = (ch, col)
        if k not in self._glyphs:
            self._glyphs[k] = text.font("kana", CELL).render(ch, True, col)
        return self._glyphs[k]

    def on_key(self, event):
        if event.key in (pygame.K_SPACE, pygame.K_RIGHT):
            self.palette = (self.palette + 1) % len(PALETTES)
            self.key = PALETTES[self.palette][0]
            self.dirty = True

    def draw_static(self, surf):
        pass    # spine only; the rain is all live

    def draw_live(self, surf, t):
        dt = 0.05 if self._last is None else min(0.2, t - self._last)
        self._last = t
        body, head = PALETTES[self.palette]
        self.layer.blit(self.fade, (0, 0), special_flags=pygame.BLEND_RGB_SUB)   # trails fade a little each frame
        for x, y, ch in self.rain.step(dt):
            if 0 <= y < self.rain.h:
                self.layer.blit(self._glyph(ch, body), (x, y))
        for c in self.rain.columns:                        # bright heads
            y = int(c.y // CELL) * CELL
            if 0 <= y < self.rain.h:
                self.layer.blit(self._glyph(GLYPHS[(c.x + y) % len(GLYPHS)], head), (c.x, y))
        surf.blit(self.layer, (X0 + 2, 0))
        return True


MODULE = Matrix
