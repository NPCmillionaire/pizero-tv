import json, os

from modules.miner import data

F = os.path.join(os.path.dirname(__file__), "fixtures")
load = lambda n: json.load(open(os.path.join(F, n)))


def test_parse_summary():
    r = data.parse_summary(load("rig.json"))
    assert r.h10 and r.h10 > 100 and r.pool.startswith("gulf.moneroocean")
    assert r.accepted >= 0 and r.rejected == 0 and "i5-6500" in r.cpu and "(R)" not in r.cpu


def test_summary_before_first_hash():
    r = data.parse_summary({"hashrate": {"total": [None, None, None]}, "connection": {}})
    assert r.h10 is None and r.accepted == 0 and r.pool == ""


def test_wallet_amounts_in_xmr_and_chart_oldest_first():
    w = data.parse_wallet({"hash": 1300.5, "amtDue": 4475244983, "amtPaid": 0, "validShares": 3},
                          [{"ts": 2000000, "hs": 2.0}, {"ts": 1000000, "hs": 1.0}])
    assert abs(w.due_xmr - 0.004475244983) < 1e-12 and w.paid_xmr == 0
    assert w.chart == [(1000, 1.0), (2000, 2.0)]


def test_gauge_scale():
    assert data.gauge_max(400) == 500 and data.gauge_max(1344) == 2000 and data.gauge_max(None) == 500


def test_lamps():
    r = data.parse_summary(load("rig.json"))
    names = dict(data.lamps(r, None))
    assert names["Pool connected"] == "ok" and names["Pool sees rig"] == "off"
    assert data.lamps(None, None) == [("Rig online", "alarm")]


def test_price():
    assert data.parse_price({"monero": {"usd": 501.62}}) == 501.62


def test_render_with_config(monkeypatch):
    import pygame
    from tests.modules.test_render_smoke import fixtures
    from tvkit import config, text
    from tvkit.module import Ctx
    from modules.miner import Miner
    monkeypatch.setattr(text, "CHECK_GLYPHS", True)
    for mode in ("live", "offline", "waiting"):
        text.OVERFLOWS.clear(); text.MISSING.clear()
        f = fixtures("miner"); f["__mode__"] = mode
        m = Miner()
        m.start(Ctx(config.Config(raw={"miner": {"url": "http://r:8081", "token": "x", "wallet": "4abc"}}), None, fakes=f))
        s = pygame.Surface((1280, 720))
        m.update(0.0); m.draw_frame(s); m.draw_static(s); m.draw_live(s, 0.6)
        m.stop()
        assert text.OVERFLOWS == [] and text.MISSING == [], mode
