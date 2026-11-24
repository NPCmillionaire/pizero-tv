"""Fonts and overflow-proof text drawing."""
import os
from functools import lru_cache

import pygame

from . import theme

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FILES = {
    "display": "BigShouldersDisplay-800.ttf",
    "display-600": "BigShouldersDisplay-600.ttf",
    "display-400": "BigShouldersDisplay-400.ttf",
    "sans": "IBMPlexSansCondensed-Regular.ttf",
    "sans-500": "IBMPlexSansCondensed-Medium.ttf",
    "sans-600": "IBMPlexSansCondensed-SemiBold.ttf",
    "mono": "IBMPlexMono-Regular.ttf",
    "mono-500": "IBMPlexMono-Medium.ttf",
    "kana": "KanaSubset.ttf",
}
OVERFLOWS = []   # test hook: (text, rect) for anything drawn past the surface edge


@lru_cache(maxsize=None)
def font(role, size):
    return pygame.font.Font(os.path.join(FONT_DIR, FILES[role]), size)


def fit(f, s, max_w):
    """Return s, truncated with an ellipsis so it renders within max_w px."""
    if f.size(s)[0] <= max_w:
        return s
    lo, hi = 0, len(s)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if f.size(s[:mid].rstrip() + "…")[0] <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return (s[:lo].rstrip() + "…") if lo else ""


@lru_cache(maxsize=2048)
def _render(role, size, s, color):
    return font(role, size).render(s, True, color)


def render(s, role="sans", size=20, color=theme.BONE, max_w=None):
    if max_w is not None:
        s = fit(font(role, size), s, max_w)
    return _render(role, size, s, tuple(color))


def draw(surf, s, pos, role="sans", size=20, color=theme.BONE, max_w=None, anchor="topleft"):
    img = render(s, role, size, color, max_w)
    r = img.get_rect(**{anchor: pos})
    if not surf.get_rect().contains(r) and r.width > 0:
        OVERFLOWS.append((s, r))
    surf.blit(img, r)
    return r


def wrap(s, role, size, max_w):
    """Greedy word wrap to lines that each render within max_w px."""
    f, lines, cur = font(role, size), [], ""
    for w in s.split():
        nxt = (cur + " " + w).strip()
        if f.size(nxt)[0] <= max_w or not cur:
            cur = nxt
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])
