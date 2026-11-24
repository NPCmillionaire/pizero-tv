"""Fonts, colors and small drawing helpers for sfdispatch."""
import os
from functools import lru_cache

import pygame

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

BG = (7, 10, 16)
PANEL = (12, 17, 26)
EDGE = (30, 40, 56)
TEXT = (226, 232, 240)
MUTED = (120, 134, 156)
DIM = (70, 82, 102)
ACCENT = (94, 200, 255)
RED = (255, 64, 72)
AMBER = (255, 170, 40)
CYAN = (70, 190, 220)
GREEN = (60, 220, 130)
PRIORITY = {"A": RED, "B": AMBER, "C": CYAN, "?": MUTED}


@lru_cache(maxsize=None)
def font(size, mono=False, bold=False):
    name = "DejaVuSans" + ("Mono" if mono else "") + ("-Bold" if bold else "") + ".ttf"
    return pygame.font.Font(os.path.join(FONT_DIR, name), size)


def fit(f, text, max_w):
    """Return text, truncated with an ellipsis so it renders within max_w px."""
    if f.size(text)[0] <= max_w:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if f.size(text[:mid].rstrip() + "…")[0] <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return (text[:lo].rstrip() + "…") if lo else ""


def text(surf, s, pos, size=16, color=TEXT, mono=False, bold=False, max_w=None, anchor="topleft"):
    f = font(size, mono, bold)
    if max_w is not None:
        s = fit(f, s, max_w)
    img = f.render(s, True, color)
    r = img.get_rect(**{anchor: pos})
    surf.blit(img, r)
    return r


def panel(surf, rect, title=None):
    pygame.draw.rect(surf, PANEL, rect, border_radius=6)
    pygame.draw.rect(surf, EDGE, rect, 1, border_radius=6)
    if title:
        x, y, w, _ = rect
        text(surf, title, (x + 14, y + 10), 12, MUTED, bold=True, max_w=w - 28)
