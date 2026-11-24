import pytest

from tvkit import text

ROLES = ["display", "display-600", "display-400", "sans", "sans-500", "sans-600", "mono", "mono-500", "kana"]


def test_fit_truncates_with_ellipsis():
    f = text.font("sans", 20)
    out = text.fit(f, "Oceanview/Merced/Ingleside · Lakeview Ave / San Jose Ave" * 2, 200)
    assert out.endswith("…") and f.size(out)[0] <= 200


def test_fit_returns_short_unchanged():
    assert text.fit(text.font("sans", 20), "Mission", 300) == "Mission"


@pytest.mark.parametrize("role", ROLES)
def test_every_role_loads(role):
    assert text.font(role, 20).size("A")[0] > 0


def test_draw_records_no_overflow_when_fitted():
    import pygame
    s = pygame.Surface((400, 100))
    text.OVERFLOWS.clear()
    r = text.draw(s, "x" * 500, (0, 0), max_w=120)
    assert r.width <= 120 and text.OVERFLOWS == []


def test_draw_without_max_w_records_offscreen_overflow():
    import pygame
    s = pygame.Surface((100, 50))
    text.OVERFLOWS.clear()
    text.draw(s, "this string is far too wide for the surface", (0, 0))
    assert len(text.OVERFLOWS) == 1


def test_wrap_lines_fit():
    lines = text.wrap("data.sf.gov isn't answering. Nothing is shown rather than a guess.", "sans", 20, 200)
    assert len(lines) > 1 and all(text.font("sans", 20).size(l)[0] <= 200 for l in lines)
