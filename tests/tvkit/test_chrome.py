import pytest

from tvkit import chrome, theme

TITLES = ["WEATHER", "MARKETS", "CRYPTO", "THREATS", "ORBIT", "AIRSPACE", "SIGNAL", "SYSTEM",
          "LAN", "MATRIX", "OUTRUN", "TRIPPY", "DISPATCH"]


@pytest.mark.parametrize("title", TITLES)
def test_spine_fits_680_for_all_titles(title):
    s = chrome.spine(title, theme.SODIUM)
    assert s.get_height() <= 680 and s.get_width() <= 150


def test_spine_uses_max_168():
    assert chrome.spine_size("LAN") == 168
    assert chrome.spine_size("DISPATCH") == 168
    assert chrome.spine_size("EXTRAORDINARILYLONG") < 168
    assert chrome.spine("EXTRAORDINARILYLONG", theme.SODIUM).get_height() <= 680


@pytest.mark.parametrize("status,age,label", [
    ("live", 5, "live"), ("stale", 720, "stale 12m"), ("stale", 7200, "stale 2h"), ("stale", 30, "stale"),
    ("stale", None, "stale"), ("offline", None, "offline"), ("waiting", None, "waiting"),
])
def test_footer_labels(status, age, label):
    assert chrome.status_label(status, age) == label


def test_theme_tokens():
    assert theme.GROUND == (0x0C, 0x1F, 0x24) and theme.BONE == (0xEE, 0xE6, 0xD3)
    assert theme.KEYS["crypto"] == (0xF7, 0xC9, 0x48)
    assert (theme.W, theme.H, theme.CONTENT_X0, theme.CONTENT_X1) == (1280, 720, 190, 1250)
