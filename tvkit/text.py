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
    # channel looks
    "geo": "Jost-500.ttf", "geo-700": "Jost-700.ttf",                 # WEATHER: local forecast
    "loud": "Bungee-Regular.ttf",                                     # CRYPTO: late-night trading
    "stencil": "SairaStencilOne-Regular.ttf",                         # THREATS: war room
    "scope": "B612Mono-Regular.ttf", "scope-700": "B612Mono-Bold.ttf",   # AIRSPACE: ATC scope
    "console": "Oxanium-500.ttf", "console-700": "Oxanium-700.ttf",   # ORBIT: mission control
    "bulletin": "Anton-Regular.ttf",                                  # SIGNAL: breaking news
    "vga": "VT323-Regular.ttf",                                       # SYSTEM: BIOS
    "term": "ShareTechMono-Regular.ttf",                              # LAN: sonar
    "list": "BarlowCondensed-Medium.ttf", "list-700": "BarlowCondensed-Bold.ttf",   # GUIDE: listings
}
OVERFLOWS = []   # test hook: (text, rect) for anything drawn past the surface edge
CHECK_GLYPHS = False   # test hook: when True, record characters a font can't draw in MISSING
MISSING = []
_CMAPS = {}


def _check(role, s):
    if role not in _CMAPS:
        from fontTools.ttLib import TTFont   # dev/test dependency only
        _CMAPS[role] = set(TTFont(os.path.join(FONT_DIR, FILES[role])).getBestCmap())
    bad = {c for c in s if ord(c) not in _CMAPS[role] and not c.isspace()}
    if bad:
        MISSING.append((role, s, "".join(sorted(bad))))


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


@lru_cache(maxsize=256)
def _render(role, size, s, color):
    return font(role, size).render(s, True, color)


def clear_cache():
    """Drop cached text surfaces (big hero numbers add up); the host calls this on every switch."""
    _render.cache_clear()
    font.cache_clear()


def render(s, role="sans", size=20, color=theme.BONE, max_w=None):
    if CHECK_GLYPHS:
        _check(role, s)
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
