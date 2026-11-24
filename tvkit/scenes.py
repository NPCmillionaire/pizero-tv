"""Scenes the host draws itself: static between channels, OSD, crash notice, standby."""
import math, textwrap, time

import numpy as np
import pygame

from . import text, theme



OSD_GREEN = (124, 255, 107)
_rng = np.random.default_rng()


def static(surf, elapsed):
    """Analog snow with a rolling bright bar — the gap between channels."""
    noise = _rng.integers(0, 256, (160, 90), dtype=np.uint8)
    bar = int((elapsed * 900) % 90)
    noise[:, max(0, bar - 6):bar] = np.minimum(255, noise[:, max(0, bar - 6):bar].astype(np.int16) + 90).astype(np.uint8)
    rgb = np.repeat(noise[:, :, None], 3, axis=2)
    rgb[:, :, 2] = np.minimum(255, rgb[:, :, 2].astype(np.int16) + 18).astype(np.uint8)   # cold CRT tint
    surf.blit(pygame.transform.scale(pygame.surfarray.make_surface(rgb), surf.get_size()), (0, 0))


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
