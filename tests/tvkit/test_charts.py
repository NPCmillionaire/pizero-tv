import pygame

from tvkit import charts, theme


def _outside_clean(surf, rect):
    r = pygame.Rect(rect)
    for x in range(0, surf.get_width(), 7):
        for y in range(0, surf.get_height(), 7):
            if not r.inflate(2, 2).collidepoint(x, y) and surf.get_at((x, y))[:3] != (0, 0, 0):
                return False
    return True


def test_sparkline_stays_inside_rect():
    s = pygame.Surface((300, 200))
    charts.sparkline(s, (50, 50, 200, 100), [5, 1, 9, 3, 7, 2], theme.SEAGLASS)
    assert _outside_clean(s, (50, 50, 200, 100))


def test_sparkline_flat_and_short_series():
    s = pygame.Surface((300, 200))
    charts.sparkline(s, (50, 50, 200, 100), [4, 4, 4], theme.SEAGLASS)
    charts.sparkline(s, (50, 50, 200, 100), [4], theme.SEAGLASS)   # too short: draws nothing, no error
    assert _outside_clean(s, (50, 50, 200, 100))


def test_candles_stay_inside_rect():
    s = pygame.Surface((400, 300))
    o, h, l, c = [10, 11, 12, 11], [12, 13, 13, 12], [9, 10, 11, 10], [11, 12, 11, 10]
    rng = charts.candles(s, (40, 40, 300, 200), o, h, l, c, ma=[None, 11, 11.5, 11])
    assert _outside_clean(s, (40, 40, 300, 200)) and rng == (9, 13)
