from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from feed import Call
from replay import Replayer, schedule

T0 = datetime(2026, 11, 23, 18, 0, tzinfo=ZoneInfo("America/Los_Angeles"))


def call(cad, sec):
    return Call(cad, T0 + timedelta(seconds=sec), None, "X", "C", "", "Mission", -122.42, 37.76)


def test_empty():
    assert schedule([], 100.0, 60.0) == []


def test_single_at_start():
    assert schedule([call("a", 5)], 100.0, 60.0) == [(100.0, call("a", 5))]


def test_order_preserved():
    b = [call("c", 40), call("a", 0), call("b", 10)]
    assert [c.cad for _, c in schedule(b, 0.0, 60.0)] == ["a", "b", "c"]


def test_spread_within_window():
    b = [call(str(i), i * 7) for i in range(20)]
    times = [t for t, _ in schedule(b, 100.0, 60.0)]
    assert all(100.0 <= t < 160.0 for t in times)


def test_proportional_gaps():
    t = [x for x, _ in schedule([call("a", 0), call("b", 10), call("c", 40)], 0.0, 60.0)]
    assert t == [0.0, 13.5, 54.0]


def test_same_timestamp_batch():
    t = [x for x, _ in schedule([call("a", 3), call("b", 3)], 0.0, 60.0)]
    assert t == [0.0, 0.0]


def test_initial_immediate():
    r = Replayer()
    r.add([call("a", 0), call("b", 900)], now=50.0, initial=True)
    assert [c.cad for c in r.due(50.0)] == ["a", "b"]


def test_due_pops_once():
    r = Replayer()
    r.add([call("a", 0), call("b", 40)], now=0.0, initial=False)
    assert [c.cad for c in r.due(1.0)] == ["a"]
    assert r.due(1.0) == []
    assert [c.cad for c in r.due(60.0)] == ["b"]
