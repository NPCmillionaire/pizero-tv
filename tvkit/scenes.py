"""Scenes the host draws itself: splash between modules, crash notice, standby."""
import math, textwrap, time

import pygame

from . import text, theme

REPO = "github.com/NPCmillionaire/pizero-tv"


def _title_size(title, max_w):
    size = 260
    while size > 60 and text.font("display", size).size(title)[0] > max_w:
        size -= 10
    return size


def splash(surf, cls, elapsed):
    """The module's spine title, unfolded: huge, horizontal, in its key color."""
    surf.fill(theme.GROUND)
    text.draw(surf, "legitbiz.research", (80, 60), "sans-600", 24, theme.BONE)
    size = _title_size(cls.title, theme.W - 160)
    # settle in: rise 24 px and fade from the ground color over 500 ms
    k = min(1.0, elapsed / 0.5)
    ease = 1 - (1 - k) ** 3
    col = theme.mix(theme.GROUND, cls.key, ease)
    r = text.draw(surf, cls.title, (72, 380 - int(24 * (1 - ease))), "display", size, col, anchor="midleft")
    text.draw(surf, cls.blurb, (80, r.bottom + 6), "sans", 26, theme.mix(theme.GROUND, theme.LICHEN, ease),
              max_w=theme.W - 160)
    text.draw(surf, REPO, (80, theme.H - 52), "mono", 16, theme.LICHEN)
    # indeterminate loading hairline: a key-colored segment sweeping the bottom edge
    span = theme.W - 160
    x = 80 + int((math.sin(elapsed * 2.2) + 1) / 2 * (span - 160))
    pygame.draw.line(surf, theme.TIDE, (80, theme.H - 24), (theme.W - 80, theme.H - 24), 2)
    pygame.draw.line(surf, cls.key, (x, theme.H - 24), (x + 160, theme.H - 24), 2)


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
