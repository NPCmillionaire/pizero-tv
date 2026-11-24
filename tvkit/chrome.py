"""Frame shared by every module: the spine, the hairline, the footer."""
from functools import lru_cache

import pygame

from . import text, theme

SPINE_MAX, SPINE_LEN = 168, 680


@lru_cache(maxsize=None)
def spine_size(title):
    size = SPINE_MAX
    while size > 40:
        if text.font("display", size).size(title)[0] <= SPINE_LEN:
            return size
        size -= 4
    return size


@lru_cache(maxsize=None)
def spine(title, key):
    img = text.font("display", spine_size(title)).render(title, True, key)
    img = pygame.transform.rotate(img, 90)
    ink = img.get_bounding_rect()          # crop the font's line-gap padding to the glyphs
    return img.subsurface(ink).copy()


def draw_frame(surf, spine_img):
    surf.fill(theme.GROUND)
    x = (theme.SPINE_W - spine_img.get_width()) // 2
    surf.blit(spine_img, (x, theme.H - 20 - spine_img.get_height()))
    pygame.draw.line(surf, theme.TIDE, (theme.SPINE_W, 0), (theme.SPINE_W, theme.H), 2)


def _ago(s):
    if s is None or s < 60:
        return ""
    m = int(s // 60)
    return f" {m}m" if m < 120 else f" {m // 60}h"


def status_label(status, age_s):
    return "stale" + _ago(age_s) if status == "stale" else status


STATUS_COLOR = {"live": theme.SEAGLASS, "stale": theme.SODIUM, "offline": theme.CORAL,
                "waiting": theme.LICHEN}


def draw_footer(surf, status, age_s):
    r = text.draw(surf, "legitbiz.research", (theme.W - 30, theme.H - 14), "sans", 14,
                  theme.LICHEN, anchor="bottomright")
    if status is None:
        return
    col = STATUS_COLOR.get(status, theme.LICHEN)
    r2 = text.draw(surf, status_label(status, age_s), (r.left - 22, r.bottom), "sans-500", 14,
                   col, anchor="bottomright")
    pygame.draw.circle(surf, col, (r2.left - 9, r2.centery + 1), 4)
