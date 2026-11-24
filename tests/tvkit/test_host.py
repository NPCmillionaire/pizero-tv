import json
import threading

import pygame
import pytest

from tvkit import config
from tvkit.host import Host
from tvkit.module import Module
from tvkit.registry import Registry


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def mod(name, **kw):
    attrs = dict(name=name, title=name.upper(), blurb=f"{name} blurb", order=len(name))
    attrs.update(kw)
    return type(name.title(), (Module,), attrs)


class Slow(Module):
    name, title, blurb = "slow", "SLOW", "never ready"
    ready = property(lambda self: False)


class Boom(Module):
    name, title, blurb = "boom", "BOOM", "crashes on draw"

    def draw_static(self, surf):
        raise RuntimeError("kaboom")


class Counting(Module):
    name, title, blurb = "count", "COUNT", "counts"
    starts = builds = 0

    def start(self, ctx):
        super().start(ctx)
        type(self).starts += 1

    def update(self, now):
        return getattr(self, "flip", False)

    def draw_static(self, surf):
        type(self).builds += 1


class WithSource(Module):
    name, title, blurb = "src", "SRC", "has a source"

    def start(self, ctx):
        super().start(ctx)
        self.source("x", lambda: 1, interval=0.01, cache=False)


def make(*classes, state_path=None):
    reg = Registry()
    for c in classes:
        reg.add(c)
    clock = Clock()
    h = Host(pygame.Surface((1280, 720)), reg, config.Config(), state_path=state_path,
             cache_root=None, clock=clock)
    return h, clock


def run(h, clock, seconds, dt=0.1):
    for _ in range(int(seconds / dt)):
        clock.t += dt
        h.step()


def test_show_runs_static_then_module():
    Counting.starts = 0
    h, c = make(Counting)
    h.show("count")
    assert h.phase == "static" and Counting.starts == 1     # data starts loading under the static
    run(h, c, 0.3)
    assert h.phase == "static"
    run(h, c, 0.2)
    assert h.phase == "module"


def test_module_shown_before_ready():
    h, c = make(Slow)
    h.show("slow")
    run(h, c, 0.6)
    assert h.phase == "module"


def test_channel_numbers_follow_order():
    a, b, cc = mod("aa", order=1), mod("bb", order=2), mod("cc", order=3)
    h, _ = make(a, b, cc)
    assert [x.name for x in h.registry.channels()] == ["aa", "bb", "cc"] and h.registry.number("bb") == 1


def test_up_down_wrap():
    a, b, cc = mod("aa", order=1), mod("bb", order=2), mod("cc", order=3)
    h, c = make(a, b, cc)
    h.show("aa")
    h.up()
    assert h.cls.name == "bb"
    h.down()
    h.down()
    assert h.cls.name == "cc"
    h.up()
    assert h.cls.name == "aa"


def test_channel_by_number():
    a, b = mod("aa", order=1), mod("bb", order=2)
    h, _ = make(a, b)
    assert h.handle("ch 1") == "ok" and h.cls.name == "bb"
    assert h.handle("ch 9").startswith("error: no channel 9")


def test_two_digit_entry():
    mods = [mod(f"m{i:02d}", order=i) for i in range(13)]
    h, c = make(*mods)
    h.show("m00")
    h.digit(1)
    run(h, c, 0.5)
    h.digit(2)
    run(h, c, 0.2)
    assert h.cls.name == "m12"


def test_single_digit_commits_after_window():
    mods = [mod(f"m{i:02d}", order=i) for i in range(13)]
    h, c = make(*mods)
    h.show("m00")
    h.digit(7)
    run(h, c, 1.0)
    assert h.cls.name == "m00"
    run(h, c, 0.4)
    assert h.cls.name == "m07"


def test_osd_visible_3s_then_fades():
    h, c = make(mod("aa"))
    h.show("aa")
    t0 = c.t
    assert h.osd_alpha(t0 + 1.0) == 255 and h.osd_alpha(t0 + 3.25) < 255 and h.osd_alpha(t0 + 4.0) == 0


def test_external_module_idles_host():
    class Ext(Module):
        name, title, blurb = "ext", "EXT", "x"
        external = True
    h, c = make(Ext)
    h.show("ext")
    run(h, c, 1.0)
    assert h.step() == 2


def test_switch_stops_previous_sources():
    a = mod("aa")
    h, c = make(WithSource, a)
    h.show("src")
    run(h, c, 0.5)
    h.show("aa")
    alive = [t for t in threading.enumerate() if t.name == "source:x" and t.is_alive()]
    assert alive == []


def test_module_crash_shows_error_scene_then_continues():
    ok = mod("okay")
    h, c = make(Boom, ok)
    h.cycle(90, ["boom", "okay"])
    run(h, c, 1.5)
    assert h.phase == "crash" and "kaboom" in h.crash_text
    run(h, c, 10.2)
    assert h.current.name == "okay"


def test_crash_in_start_is_contained():
    class BadStart(Module):
        name, title, blurb = "badstart", "BAD", "x"

        def start(self, ctx):
            raise ValueError("nope")
    h, c = make(BadStart)
    h.show("badstart")
    run(h, c, 0.3)
    assert h.phase == "crash"


def test_static_rebuilt_only_when_update_true():
    Counting.builds = 0
    h, c = make(Counting)
    h.show("count")
    run(h, c, 2.0)
    n = Counting.builds
    run(h, c, 2.0)
    assert Counting.builds == n
    h.current.flip = True
    run(h, c, 0.2)
    assert Counting.builds > n


def test_cycle_advances_after_seconds():
    a, b = mod("aa"), mod("bbb")
    h, c = make(a, b)
    h.cycle(30, None)
    run(h, c, 2)
    assert h.current.name == "aa"
    run(h, c, 30)
    assert h.current.name == "bbb"
    run(h, c, 32)
    assert h.current.name == "aa"


def test_state_persisted_and_resumed(tmp_path):
    a, b = mod("aa"), mod("bbb")
    sp = tmp_path / "state.json"
    h, c = make(a, b, state_path=str(sp))
    h.cycle(45, ["bbb", "aa"])
    st = json.load(open(sp))
    assert st == {"mode": "cycle", "module": "bbb", "cycle_seconds": 45, "cycle_names": ["bbb", "aa"]}
    h2, _ = make(a, b, state_path=str(sp))
    h2.resume()
    assert h2.mode == "cycle" and h2.current.name == "bbb" and h2.cycle_seconds == 45


def test_state_unknown_module_falls_back(tmp_path):
    a = mod("aa")
    sp = tmp_path / "state.json"
    sp.write_text(json.dumps({"mode": "show", "module": "gone"}))
    h, _ = make(a, state_path=str(sp))
    h.resume()
    assert h.mode == "cycle" and h.current.name == "aa"


def test_standby_stops_module():
    h, c = make(WithSource)
    h.show("src")
    run(h, c, 0.3)
    h.standby()
    assert h.current is None and h.phase == "standby"
    run(h, c, 1)


@pytest.mark.parametrize("line,expect", [
    ("show aa", "ok"), ("next", "ok"), ("stop", "ok"), ("cycle 20 aa", "ok"),
    ("show nope", "error: unknown module nope"), ("dance", "error: unknown command dance"),
])
def test_handle_commands(line, expect):
    h, _ = make(mod("aa"))
    assert h.handle(line).startswith(expect)


def test_status_json():
    h, c = make(mod("aa"))
    h.show("aa")
    s = json.loads(h.handle("status"))
    assert s["module"] == "aa" and s["mode"] == "show" and "phase" in s


def test_cycle_with_one_module_does_not_restart_it():
    Counting.starts = 0
    h, c = make(Counting)
    h.cycle(30, None)
    run(h, c, 70)
    assert Counting.starts == 1 and h.phase == "module"


def test_module_can_lower_its_active_fps():
    class Art(Module):
        name, title, blurb, fps = "art", "ART", "x", 15

        def draw_live(self, surf, t):
            return True
    h, c = make(Art)
    h.show("art")
    run(h, c, 1.5)
    assert h.step() == 15
