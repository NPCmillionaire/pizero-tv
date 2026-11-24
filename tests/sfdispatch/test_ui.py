import pygame

import ui


def setup_module():
    pygame.init()


def test_fit_truncates():
    f = ui.font(16)
    s = "SUTTER ST \\ VAN NESS AVE" * 3
    out = ui.fit(f, s, 120)
    assert out.endswith("…")
    assert f.size(out)[0] <= 120


def test_fit_short_unchanged():
    f = ui.font(16)
    assert ui.fit(f, "Mission", 300) == "Mission"


def test_fit_tiny_width():
    f = ui.font(16)
    assert f.size(ui.fit(f, "Tenderloin", 5))[0] <= 5 or ui.fit(f, "Tenderloin", 5) == ""
