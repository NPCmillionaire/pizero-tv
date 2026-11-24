import pygame

from tvkit import world


def test_projection_corners():
    p = world.Projection((0, 0, 1000, 500))
    x0, y0 = p.to_px(-180, world.LAT_MAX)
    x1, y1 = p.to_px(180, world.LAT_MIN)
    assert (x0, y0) == (0, 0) and abs(x1 - 1000) <= 1 and y1 <= 500


def test_projection_clamps_latitude():
    p = world.Projection((0, 0, 1000, 500))
    assert p.to_px(0, 89.9)[1] == p.to_px(0, world.LAT_MAX)[1]


def test_country_lookup():
    assert world.country("US")["name"] == "United States of America"
    assert world.country("ZZ") is None


def test_render_returns_surface_of_rect_size():
    s = world.render((0, 0, 600, 300), (20, 40, 50), (30, 60, 70))
    assert s.get_size() == (600, 300)
