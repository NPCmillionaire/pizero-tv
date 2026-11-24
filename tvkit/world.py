"""World map: Natural Earth countries in an equirectangular projection (Antarctica cropped)."""
import json, os
from functools import lru_cache

import pygame

LAT_MAX, LAT_MIN = 84.0, -58.0
PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "world.json")


@lru_cache(maxsize=1)
def _data():
    with open(PATH) as fh:
        return json.load(fh)["countries"]


@lru_cache(maxsize=None)
def _by_iso():
    return {c["iso"]: c for c in _data()}


def country(iso):
    return _by_iso().get(iso)


def countries():
    return _data()


class Projection:
    def __init__(self, rect):
        self.x, self.y, self.w, self.h = rect

    def to_px(self, lon, lat):
        lat = max(LAT_MIN, min(LAT_MAX, lat))
        return (round(self.x + (lon + 180) / 360 * self.w),
                round(self.y + (LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * self.h))


def height_for(width):
    """Rect height that keeps degrees square for a given width."""
    return round(width * (LAT_MAX - LAT_MIN) / 360)


def render(rect, fill, edge=None, highlight=None):
    """Surface the size of rect with every country drawn. highlight: {iso: color} overrides fill."""
    w, h = rect[2], rect[3]
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    p = Projection((0, 0, w, h))
    for c in _data():
        if c["iso"] == "AQ":
            continue
        col = (highlight or {}).get(c["iso"], fill)
        for ring in c["rings"]:
            pts = [p.to_px(x, y) for x, y in ring]
            if len(pts) >= 3:
                pygame.draw.polygon(surf, col, pts)
                if edge:
                    pygame.draw.lines(surf, edge, True, pts, 1)
    return surf
