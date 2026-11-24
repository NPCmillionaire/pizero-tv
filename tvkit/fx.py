"""Broadcast effects shared by the channel looks: gradients, ticker crawls, scanlines, glow.

Everything here is pre-rendered once and blitted, so a Pi Zero can afford it at 24 FPS.
"""
from functools import lru_cache

import pygame

from . import text


@lru_cache(maxsize=16)
def gradient(size, top, bottom):
    """A vertical gradient surface from `top` (row 0) to `bottom` (last row)."""
    w, h = size
    col = pygame.Surface((1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        col.set_at((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return pygame.transform.scale(col, (w, h))


def clear_cache():
    gradient.cache_clear()
    _glow.cache_clear()


def scanlines(surf, strength=60, every=2):
    """Darken every `every`th row, CRT style (applied to the static layer, so drawn once)."""
    w, h = surf.get_size()
    line = pygame.Surface((w, 1))
    line.fill((strength, strength, strength))
    for y in range(1, h, every):
        surf.blit(line, (0, y), special_flags=pygame.BLEND_RGB_SUB)


@lru_cache(maxsize=64)
def _glow(s, role, size, color, halo, radius):
    if text.CHECK_GLYPHS:
        text._check(role, s)
    f = text.font(role, size)
    core = f.render(s, True, color)
    w, h = core.get_width() + radius * 4, core.get_height() + radius * 4
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    glow = pygame.Surface((w, h), pygame.SRCALPHA)
    glow.blit(f.render(s, True, halo), (radius * 2, radius * 2))
    k = radius + 1
    glow = pygame.transform.smoothscale(pygame.transform.smoothscale(glow, (max(1, w // k), max(1, h // k))), (w, h))
    out.blit(glow, (0, 0))
    out.blit(core, (radius * 2, radius * 2))
    return out


def glow_text(s, role, size, color, radius=3, halo=None):
    """Text with a soft neon/phosphor halo (in `halo`, default the text color), on a transparent surface."""
    return _glow(s, role, size, tuple(color), tuple(halo or color), radius)


class Crawl:
    """A news-ticker strip: items rendered once, scrolled right-to-left inside a band."""

    def __init__(self, items, role, size, color, speed=90, sep="   ·   ", sep_color=None):
        self.speed = speed
        f = text.font(role, size)
        parts = []
        for it in items:                     # an item is text, (text, color), or a list of (text, color) runs
            runs = it if isinstance(it, list) else [it if isinstance(it, tuple) else (it, color)]
            for run, col in runs:
                if text.CHECK_GLYPHS:
                    text._check(role, run)
                parts.append(f.render(run, True, col))
            parts.append(f.render(sep, True, sep_color or color))
        if not parts:
            self.strip = None
            return
        w = sum(p.get_width() for p in parts)
        self.strip = pygame.Surface((w, max(p.get_height() for p in parts)), pygame.SRCALPHA)
        x = 0
        for p in parts:
            self.strip.blit(p, (x, 0))
            x += p.get_width()

    def offset(self, t):
        return t * self.speed

    def draw(self, surf, rect, t):
        if self.strip is None:
            return
        sw = self.strip.get_width()
        x = rect.left - int(self.offset(t)) % sw
        y = rect.top + (rect.height - self.strip.get_height()) // 2
        prev = surf.get_clip()
        surf.set_clip(rect.clip(prev) if prev else rect)
        while x < rect.right:
            surf.blit(self.strip, (x, y))
            x += sw
        surf.set_clip(prev)
