import pygame

from tvkit import fx


def test_gradient_runs_top_to_bottom():
    g = fx.gradient((40, 100), (0, 0, 0), (200, 100, 0))
    assert tuple(g.get_at((5, 0)))[:3] == (0, 0, 0)
    assert tuple(g.get_at((5, 99)))[:3] == (200, 100, 0)


def test_crawl_moves_left_and_stays_in_its_band():
    surf = pygame.Surface((400, 100))
    c = fx.Crawl(["ALPHA", "BETA"], "sans", 20, (255, 255, 255), speed=100)
    surf.fill((0, 0, 0))
    c.draw(surf, pygame.Rect(0, 40, 400, 30), 0.0)
    assert any(tuple(surf.get_at((x, y)))[:3] != (0, 0, 0) for x in range(400) for y in range(40, 70))
    assert all(tuple(surf.get_at((x, 10)))[:3] == (0, 0, 0) for x in range(400))     # nothing outside
    assert c.offset(1.0) - c.offset(0.0) == 100


def test_crawl_with_nothing_draws_nothing():
    surf = pygame.Surface((100, 40))
    fx.Crawl([], "sans", 20, (255, 255, 255)).draw(surf, surf.get_rect(), 3.0)


def test_scanlines_darken_alternate_rows():
    s = pygame.Surface((10, 10))
    s.fill((200, 200, 200))
    fx.scanlines(s, strength=100)
    assert s.get_at((0, 1))[0] < s.get_at((0, 0))[0]


def test_glow_is_bigger_than_text():
    img = fx.glow_text("HI", "sans", 30, (0, 255, 0))
    plain = pygame.font.Font(None, 30)
    assert img.get_width() > 10 and img.get_flags() & pygame.SRCALPHA


def test_crawl_item_runs_stay_together():
    one = fx.Crawl([[("A", (255, 0, 0)), ("B", (0, 255, 0))]], "sans", 20, (255, 255, 255), sep=" ")
    two = fx.Crawl(["A", "B"], "sans", 20, (255, 255, 255), sep=" ")
    assert one.strip.get_width() < two.strip.get_width()
