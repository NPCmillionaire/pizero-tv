"""Weather icons drawn with primitives — no emoji, no missing-glyph boxes."""
import math

import pygame

from tvkit import theme


def _cloud(surf, cx, cy, s, color):
    for dx, dy, r in ((-0.28, 0.08, 0.26), (0.0, -0.08, 0.34), (0.3, 0.06, 0.25)):
        pygame.draw.circle(surf, color, (cx + int(dx * s), cy + int(dy * s)), int(r * s))
    pygame.draw.rect(surf, color, (cx - int(0.5 * s), cy + int(0.06 * s), int(1.0 * s), int(0.26 * s)),
                     border_radius=int(0.13 * s))


def _sun(surf, cx, cy, s, color, rays=True):
    pygame.draw.circle(surf, color, (cx, cy), int(0.26 * s))
    if rays:
        for i in range(8):
            a = i * math.pi / 4
            r0, r1 = 0.36 * s, 0.5 * s
            pygame.draw.line(surf, color, (cx + r0 * math.cos(a), cy + r0 * math.sin(a)),
                             (cx + r1 * math.cos(a), cy + r1 * math.sin(a)), max(2, int(s * 0.06)))


def _moon(surf, cx, cy, s, color, bg):
    pygame.draw.circle(surf, color, (cx, cy), int(0.32 * s))
    pygame.draw.circle(surf, bg, (cx + int(0.16 * s), cy - int(0.1 * s)), int(0.28 * s))


def _drops(surf, cx, cy, s, color, n=3, length=0.22, slant=0.08):
    w = max(2, int(s * 0.05))
    for i in range(n):
        x = cx + int((i - (n - 1) / 2) * 0.24 * s)
        y = cy + int(0.42 * s)
        pygame.draw.line(surf, color, (x, y), (x - int(slant * s), y + int(length * s)), w)


def _flakes(surf, cx, cy, s, color):
    for i in range(3):
        x = cx + int((i - 1) * 0.26 * s)
        y = cy + int(0.5 * s) + (int(0.08 * s) if i == 1 else 0)
        r = max(2, int(0.05 * s))
        for a in range(3):
            ang = a * math.pi / 3
            pygame.draw.line(surf, color, (x - r * 1.6 * math.cos(ang), y - r * 1.6 * math.sin(ang)),
                             (x + r * 1.6 * math.cos(ang), y + r * 1.6 * math.sin(ang)), max(1, r // 2))


def draw(surf, icon, center, size, night=False, bg=theme.GROUND, muted=False):
    """Draw `icon` (see data.ICONS) centered in a size×size box. muted: quieter colors for small rows."""
    cx, cy = center
    sun_col, cloud_col, wet = theme.SODIUM, theme.BONE, (127, 178, 255)
    if muted:
        cloud_col = theme.mix(theme.GROUND, theme.BONE, 0.55)
    if icon == "sun":
        if night:
            _moon(surf, cx, cy, size, cloud_col, bg)
        else:
            _sun(surf, cx, cy, size, sun_col)
    elif icon == "moon":
        _moon(surf, cx, cy, size, cloud_col, bg)
    elif icon == "partly":
        if night:
            _moon(surf, cx - int(0.18 * size), cy - int(0.18 * size), int(size * 0.8), theme.LICHEN, bg)
        else:
            _sun(surf, cx - int(0.18 * size), cy - int(0.2 * size), int(size * 0.75), sun_col)
        _cloud(surf, cx + int(0.06 * size), cy + int(0.08 * size), int(size * 0.8), cloud_col)
    elif icon == "cloud":
        _cloud(surf, cx, cy, size, cloud_col)
    elif icon == "fog":
        w = max(2, int(size * 0.06))
        for i, k in enumerate((0.8, 1.0, 0.7)):
            y = cy + int((i - 1) * 0.2 * size)
            pygame.draw.line(surf, theme.LICHEN, (cx - k * 0.45 * size, y), (cx + k * 0.45 * size, y), w)
    elif icon in ("drizzle", "rain", "showers"):
        _cloud(surf, cx, cy - int(0.12 * size), int(size * 0.85), cloud_col)
        _drops(surf, cx, cy - int(0.12 * size), size, wet, n=2 if icon == "drizzle" else 3,
               length=0.14 if icon == "drizzle" else 0.24)
        if icon == "showers" and not night:
            _sun(surf, cx + int(0.32 * size), cy - int(0.36 * size), int(size * 0.4), sun_col, rays=False)
    elif icon == "snow":
        _cloud(surf, cx, cy - int(0.12 * size), int(size * 0.85), cloud_col)
        _flakes(surf, cx, cy - int(0.12 * size), size, cloud_col)
    elif icon == "thunder":
        _cloud(surf, cx, cy - int(0.14 * size), int(size * 0.85), theme.LICHEN)
        s = size
        bolt = [(cx + 0.02 * s, cy + 0.02 * s), (cx - 0.14 * s, cy + 0.3 * s), (cx + 0.0 * s, cy + 0.3 * s),
                (cx - 0.08 * s, cy + 0.52 * s), (cx + 0.16 * s, cy + 0.22 * s), (cx + 0.02 * s, cy + 0.22 * s),
                (cx + 0.12 * s, cy + 0.02 * s)]
        pygame.draw.polygon(surf, sun_col, bolt)
