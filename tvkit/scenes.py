"""Scenes the host draws itself: static between channels, OSD, crash notice, standby."""
import math, textwrap, time

import numpy as np
import pygame

from . import text, theme



OSD_GREEN = (124, 255, 107)
STATION_TAG = "legitbiz{research}"
_rng = np.random.default_rng()


_FRAMES = []
NOISE_W, NOISE_H, NOISE_FRAMES = 426, 240, 10


def _noise_frames():
    """A few pre-made low-res snow frames; flipping through them is cheap enough for a Pi Zero."""
    if not _FRAMES:
        for _ in range(NOISE_FRAMES):
            n = _rng.integers(0, 256, (NOISE_W, NOISE_H), dtype=np.uint8)
            rgb = np.repeat(n[:, :, None], 3, axis=2)
            rgb[:, :, 2] = np.minimum(255, rgb[:, :, 2].astype(np.int16) + 18).astype(np.uint8)   # cold CRT tint
            _FRAMES.append(pygame.surfarray.make_surface(rgb))
    return _FRAMES


def static(surf, elapsed):
    """Analog snow that actually moves: a new frame each draw, rolled vertically, with a sync bar."""
    frames = _noise_frames()
    src = frames[int(_rng.integers(0, len(frames)))]
    w, h = surf.get_size()
    big = pygame.transform.scale(src, (w, h))
    roll = int(_rng.integers(0, h))                       # vertical hold slipping
    surf.blit(big, (0, roll - h))
    surf.blit(big, (0, roll))
    bar_y = int((elapsed * 1400) % h)                     # the bright rolling bar
    band = pygame.Surface((w, 46), pygame.SRCALPHA)
    band.fill((255, 255, 255, 70))
    surf.blit(band, (0, bar_y - 23))
    for _ in range(3):                                    # a few torn scanlines
        y = int(_rng.integers(0, h - 2))
        dx = int(_rng.integers(-40, 40))
        line = surf.subsurface((0, y, w, 2)).copy()
        surf.blit(line, (dx, y))
    # station ident through the snow, with a little horizontal sync jitter
    img = text.render(STATION_TAG, "display", 96, theme.BONE)
    jitter = int(_rng.integers(-6, 7))
    box = pygame.Rect(0, 0, img.get_width() + 60, img.get_height() + 16)
    box.center = (surf.get_width() // 2 + jitter, surf.get_height() // 2)
    plate = pygame.Surface(box.size, pygame.SRCALPHA)
    plate.fill((4, 10, 12, 190))
    surf.blit(plate, box)
    return text.draw(surf, STATION_TAG, box.center, "display", 96, theme.BONE, anchor="center")


def osd(surf, number, title, alpha=255):
    """Old-TV on-screen display, top right: CH 04  MARKETS."""
    label = f"CH {number:02d}  {title}" if number is not None else title
    img = text.render(label, "mono-500", 34, OSD_GREEN)
    pad = 14
    box = pygame.Surface((img.get_width() + 2 * pad, img.get_height() + pad), pygame.SRCALPHA)
    box.fill((0, 0, 0, int(150 * alpha / 255)))
    img = img.copy()
    img.set_alpha(alpha)
    box.blit(img, (pad, pad // 2))
    surf.blit(box, (theme.W - box.get_width() - 30, 26))


def crash(surf, name, message, remaining):
    surf.fill(theme.GROUND)
    text.draw(surf, "legitbiz.research", (80, 60), "sans-600", 24, theme.BONE)
    text.draw(surf, "This screen crashed", (76, 170), "display", 110, theme.CORAL)
    text.draw(surf, f"{name} raised an error, so the host moved past it. The details are in the log.",
              (80, 310), "sans", 24, theme.LICHEN, max_w=theme.W - 160)
    y = 370
    for line in textwrap.wrap(message, 90)[:8]:
        text.draw(surf, line, (80, y), "mono", 18, theme.BONE, max_w=theme.W - 160)
        y += 28
    text.draw(surf, f"Next screen in {max(0, math.ceil(remaining))} s", (80, theme.H - 52), "sans-500", 18,
              theme.SODIUM)


def standby(surf, now_struct=None):
    t = now_struct or time.localtime()
    surf.fill(theme.GROUND)
    text.draw(surf, time.strftime("%H:%M", t), (72, 340), "display", 240, theme.TIDE, anchor="midleft")
    text.draw(surf, "Standing by. Run tv <module> or tv cycle to wake the screen.", (80, 480),
              "sans", 24, theme.LICHEN, max_w=theme.W - 160)
    text.draw(surf, "legitbiz.research", (80, theme.H - 52), "sans-600", 18, theme.LICHEN)
