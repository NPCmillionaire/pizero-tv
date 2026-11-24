import pytest

from modules.syshud import data


def test_cpu_history_window_60():
    h = data.History(60)
    for i in range(100):
        h.add(i)
    assert len(h.values) == 60 and h.values[0] == 40 and h.values[-1] == 99


@pytest.mark.parametrize("raw,temp", [("temp=50.1'C\n", 50.1), ("temp=38.0'C", 38.0)])
def test_parse_vcgencmd_temp(raw, temp):
    assert data.parse_vcgencmd_temp(raw) == temp


def test_parse_sysfs_temp():
    assert data.parse_sysfs_temp("50123\n") == 50.123


@pytest.mark.parametrize("raw,now,since", [
    ("throttled=0x0", [], []),
    ("throttled=0x50005", ["under-voltage", "throttled"], ["under-voltage", "throttled"]),
    ("throttled=0x50000", [], ["under-voltage", "throttled"]),
    ("throttled=0x80008", ["soft temperature limit"], ["soft temperature limit"]),
])
def test_throttle_flags(raw, now, since):
    f = data.parse_throttled(raw)
    assert f["now"] == now and f["since_boot"] == since


def test_throttle_garbage_raises():
    with pytest.raises(ValueError):
        data.parse_throttled("VCHI initialization failed")


def test_rates():
    prev = {"t": 10.0, "rx": 1000, "tx": 500}
    cur = {"t": 12.0, "rx": 5000, "tx": 900}
    assert data.rates(prev, cur) == (2000.0, 200.0)
    assert data.rates(None, cur) == (None, None)


@pytest.mark.parametrize("secs,txt", [(59, "under a minute"), (3600 * 5 + 120, "5 hours, 2 minutes"),
                                      (86400 + 3600 * 2, "1 day, 2 hours"), (86400 * 3, "3 days, 0 hours")])
def test_uptime_text(secs, txt):
    assert data.uptime_text(secs) == txt


@pytest.mark.parametrize("b,txt", [(512, "512 B/s"), (2048, "2.0 KB/s"), (3.5 * 1024 * 1024, "3.5 MB/s")])
def test_human_rate(b, txt):
    assert data.human_rate(b) == txt


def test_hosts_from_config():
    from modules.syshud import data
    raw = {"system": {"hosts": [{"name": "darwin", "url": "http://darwin.local:8765"}, {"name": "broken"},
                                {"url": "http://x"}, "junk", {"name": "arch", "url": "http://arch.lan:8765/"}]}}
    assert data.hosts(raw) == [("darwin", "http://darwin.local:8765"), ("arch", "http://arch.lan:8765")]
    assert data.hosts({}) == [] and data.hosts({"system": "nope"}) == []


def test_render_with_other_machines(monkeypatch):
    import pygame
    from tests.modules.test_render_smoke import fixtures
    from tvkit import config, text
    from tvkit.module import Ctx
    from modules.syshud import System
    monkeypatch.setattr(text, "CHECK_GLYPHS", True)
    text.OVERFLOWS.clear(); text.MISSING.clear()
    cfg = config.Config(raw={"system": {"hosts": [{"name": "darwin", "url": "http://d:8765"},
                                                  {"name": "arch", "url": "http://a:8765"},
                                                  {"name": "gone", "url": "http://g:8765"}]}})
    m = System()
    m.start(Ctx(cfg, None, fakes=fixtures("syshud")))
    s = pygame.Surface((1280, 720))
    m.update(0.0); m.draw_frame(s); m.draw_static(s); m.draw_live(s, 1.0)
    m.stop()
    assert [p[0] for p in m.panels()] == ["pizero", "darwin", "arch", "gone"]
    assert text.OVERFLOWS == [] and text.MISSING == []
