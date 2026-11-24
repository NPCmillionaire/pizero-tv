import math
from geo import BBOX, Projector

RECT = (0, 0, 860, 520)


def test_corners_inside_rect():
    p = Projector(RECT)
    x0, y0, w, h = RECT
    for lon in (BBOX[0], BBOX[2]):
        for lat in (BBOX[1], BBOX[3]):
            x, y = p.to_px(lon, lat)
            assert x0 <= x <= x0 + w and y0 <= y <= y0 + h


def test_aspect_preserved():
    p = Projector(RECT)
    xa, ya = p.to_px(BBOX[0], BBOX[3])
    xb, yb = p.to_px(BBOX[2], BBOX[1])
    geo_ratio = (BBOX[2] - BBOX[0]) * math.cos(math.radians(37.76)) / (BBOX[3] - BBOX[1])
    assert abs((xb - xa) / (yb - ya) - geo_ratio) / geo_ratio < 0.01


def test_north_is_up():
    p = Projector(RECT)
    _, y_south = p.to_px(-122.42, 37.72)
    _, y_north = p.to_px(-122.42, 37.80)
    assert y_north < y_south


def test_outside_bbox():
    p = Projector(RECT)
    assert p.to_px(0, 0) is None
    assert p.to_px(-122.42, 37.90) is None
