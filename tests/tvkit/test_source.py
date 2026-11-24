import json

from tvkit.source import Source


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make(fetch, tmp_path=None, clock=None, parse=lambda x: x):
    c = clock or Clock()
    return Source("s", fetch, interval=60, parse=parse,
                  cache_dir=str(tmp_path) if tmp_path else None, clock=c, wall=c), c


def test_source_waiting_before_first_poll():
    s, _ = make(lambda: 1)
    assert s.status == "waiting" and s.value is None and s.age_s is None


def test_source_live_after_poll():
    s, _ = make(lambda: {"x": 1})
    s.poll_once()
    assert s.status == "live" and s.value == {"x": 1} and s.version == 1 and s.age_s == 0


def test_source_fetch_raises_offline():
    def boom():
        raise ConnectionError("down")
    s, _ = make(boom)
    s.poll_once()
    assert s.status == "offline" and s.value is None


def test_source_bad_payload_keeps_last_good():
    payloads = iter([{"ok": 1}, "<html>"])

    def parse(p):
        return p["ok"]
    s, _ = make(lambda: next(payloads), parse=parse)
    s.poll_once()
    s.poll_once()
    assert s.value == 1 and s.status == "stale" and s.version == 1


def test_source_stale_after_3_intervals():
    s, c = make(lambda: 5)
    s.poll_once()
    c.t += 181
    assert s.status == "stale" and s.age_s == 181


def test_source_cache_roundtrip(tmp_path):
    s, c = make(lambda: {"a": [1, 2]}, tmp_path)
    s.poll_once()
    assert json.load(open(tmp_path / "s.json"))["payload"] == {"a": [1, 2]}
    s2, _ = make(lambda: None, tmp_path, clock=c)
    assert s2.value == {"a": [1, 2]} and s2.status == "stale"


def test_source_corrupt_cache_ignored(tmp_path):
    (tmp_path / "s.json").write_text("{not json")
    s, _ = make(lambda: 1, tmp_path)
    assert s.value is None and s.status == "waiting"


def test_source_stop_joins_thread():
    import threading
    s, _ = make(lambda: 1)
    s.start()
    s.stop()
    assert not any(t.name == "source:s" and t.is_alive() for t in threading.enumerate())


def test_fresh_cache_delays_first_fetch(tmp_path):
    import time as _t
    calls = []
    s, c = make(lambda: calls.append(1) or {"a": 1}, tmp_path)
    s.poll_once()
    calls.clear()
    s2 = Source("s", lambda: calls.append(1) or {"a": 1}, interval=60, cache_dir=str(tmp_path), clock=c, wall=c)
    s2.start()
    _t.sleep(0.2)
    s2.stop()
    assert calls == [] and s2.value == {"a": 1}


def test_module_stop_does_not_wait_for_slow_fetch():
    import time as _t
    from tvkit import config
    from tvkit.module import Ctx, Module
    m = Module()
    m.start(Ctx(config.Config(), None))
    for i in range(4):
        m.source(f"slow{i}", lambda: _t.sleep(3) or 1, 60, cache=False)
    _t.sleep(0.05)
    t0 = _t.time()
    m.stop()
    assert _t.time() - t0 < 1.0


def test_repeated_failures_are_logged_once_until_recovery(capsys):
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        if calls["n"] <= 3 or calls["n"] == 5:
            raise ConnectionError("refused")
        return {"ok": 1}
    s, _ = make(fetch)
    for _ in range(5):
        s.poll_once()
    err = capsys.readouterr().err
    assert err.count("refused") == 2                  # once for the first outage, once for the second
    assert "back" in err
