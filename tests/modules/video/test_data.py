import json, os

import pytest

from modules.video import data

D = os.path.join(os.path.dirname(__file__), "fixtures")
CP = json.load(open(os.path.join(D, "listing_computerphile.json")))
SH = json.load(open(os.path.join(D, "listing_shorts.json")))


def test_parse_listing():
    e = data.parse_listing({"entries": CP["entries"] + SH["entries"]})
    assert len(e) == 50 and e[0].id == "BHOw09O3ZsI" and e[0].title == "Atomic Operations - Computerphile"
    assert e[0].url == "https://www.youtube.com/watch?v=BHOw09O3ZsI"


def test_parse_listing_skips_unavailable():
    bad = {"entries": [{"id": None, "title": "[Private video]"}, {"id": "x1", "title": "[Deleted video]"}] + CP["entries"][:2]}
    assert [x.id for x in data.parse_listing(bad)] == [CP["entries"][0]["id"], CP["entries"][1]["id"]]


def test_parse_listing_empty_raises():
    with pytest.raises(ValueError):
        data.parse_listing({"entries": []})


def test_pick_avoids_recent():
    e = data.parse_listing({"entries": CP["entries"][:12]})
    recent = [x.id for x in e[:10]]
    for seed in range(20):
        assert data.pick(e, recent, seed=seed).id in {e[10].id, e[11].id}


def test_pick_when_everything_is_recent():
    e = data.parse_listing({"entries": CP["entries"][:3]})
    assert data.pick(e, [x.id for x in e], seed=1).id in {x.id for x in e}


def test_strip_channel_suffix():
    assert data.clean_title("Atomic Operations - Computerphile") == "Atomic Operations"
    assert data.clean_title("Does adding helium reduce a balloon’s mass?") == "Does adding helium reduce a balloon’s mass?"


def test_mpv_args():
    e = data.parse_listing({"entries": CP["entries"][:1]})[0]
    a = data.mpv_args(e, 14, "COMPUTERPHILE", ytdl="/home/u/.local/bin/yt-dlp", input_conf="/tmp/in.conf")
    assert a[0] == "mpv" and "--fs" in a and a[-1] == e.url
    assert "--ytdl-format=bv*[height<=480][vcodec^=avc1]+ba/b[height<=480]" in a
    assert "--hwdec=v4l2m2m-copy" in a and "--vo=gpu" in a and "--gpu-context=wayland" in a
    assert "--profile=fast" in a and "--framedrop=vo" in a
    assert "--script-opts=ytdl_hook-ytdl_path=/home/u/.local/bin/yt-dlp" in a
    assert any(x.startswith("--osd-playing-msg=CH 14  COMPUTERPHILE") for x in a)
    assert "--input-conf=/tmp/in.conf" in a


def test_input_conf_maps_remote_keys():
    conf = data.input_conf("/home/u/pizero-tv/bin/tv")
    assert 'UP run "/home/u/pizero-tv/bin/tv" up' in conf and 'q ignore' in conf
    assert 'KP3 run "/home/u/pizero-tv/bin/tv" digit 3' in conf and '3 run "/home/u/pizero-tv/bin/tv" digit 3' in conf


def _ctx(fakes):
    from tvkit import config
    from tvkit.module import Ctx
    return Ctx(config.Config(), None, fakes=fakes)


def test_video_without_mpv_shows_message(monkeypatch):
    import shutil
    import modules.video as video
    monkeypatch.setattr(shutil, "which", lambda name: None)
    m = video.MODULES[0]()
    m.start(_ctx({"listing": CP}))
    assert "needs mpv" in m.problem and not m.external
    m.stop()


def test_stop_kills_player(monkeypatch):
    import os
    import modules.video as video

    class FakeProc:
        pid, killed = 4242, []

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            FakeProc.killed.append("term")

        def kill(self):
            FakeProc.killed.append("kill")
    monkeypatch.setattr(os, "killpg", lambda pid, sig: FakeProc.killed.append(("killpg", pid, sig)))
    m = video.MODULES[0]()
    m.start(_ctx({"listing": CP}))
    m.proc = FakeProc()
    assert m.external
    m.stop()
    assert ("killpg", 4242, 15) in FakeProc.killed


def test_config_adds_channels(tmp_path, monkeypatch):
    from tvkit import config
    p = tmp_path / "c.toml"
    p.write_text('[[video]]\nname = "numberphile"\ntitle = "NUMBERPHILE"\nurl = "https://www.youtube.com/@numberphile/videos"\n')
    monkeypatch.setattr(config, "DEFAULT_PATH", str(p))
    import importlib
    import modules.video as video
    v = importlib.reload(video)
    assert [m.name for m in v.MODULES] == ["computerphile", "shorts", "numberphile"]
    monkeypatch.undo()
    importlib.reload(video)


def test_stop_during_launch_still_kills_player(monkeypatch):
    import os, subprocess, threading, time
    import modules.video as video
    killed = []

    class SlowProc:
        pid = 777

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    def slow_popen(*a, **k):
        time.sleep(0.2)
        return SlowProc()
    monkeypatch.setattr(subprocess, "Popen", slow_popen)
    monkeypatch.setattr(os, "killpg", lambda pid, sig: killed.append(pid))
    m = video.MODULES[0]()
    m.start(_ctx({"listing": CP}))
    e = m.listing.value[0]
    t = threading.Thread(target=m._launch, args=(e,))
    t.start()
    time.sleep(0.05)
    m.stop()
    t.join()
    assert 777 in killed


def test_launch_after_stop_does_nothing(monkeypatch):
    import subprocess
    import modules.video as video
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("launched")))
    m = video.MODULES[0]()
    m.start(_ctx({"listing": CP}))
    m.stop()
    assert m._launch(m.listing.value[0]) is None


def test_missing_ytdlp_says_so(monkeypatch):
    import shutil
    import modules.video as video
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/mpv" if n == "mpv" else None)
    monkeypatch.setattr(video, "ytdlp_path", lambda: None)
    m = video.MODULES[0]()
    m.start(_ctx({"listing": CP}))
    assert "yt-dlp" in m.problem
    m.stop()


def test_orphan_pattern_matches_our_mpv():
    import modules.video as video
    e = data.parse_listing({"entries": CP["entries"][:1]})[0]
    args = data.mpv_args(e, 14, "X", ytdl="y", input_conf="/home/u/.cache/pizero-tv/computerphile/mpv-input.conf")
    import re
    assert re.search(video.ORPHAN_PATTERN, " ".join(args))


def test_parse_multi_json_lines():
    out = json.dumps(CP) + "\n" + json.dumps(SH) + "\n\n"
    assert len(data.parse_json_lines(out)) == 50
    assert data.parse_json_lines("not json\n" + json.dumps(SH)) == SH["entries"]


def test_mpv_args_turn_on_english_captions():
    e = data.parse_listing({"entries": CP["entries"][:1]})[0]
    a = data.mpv_args(e, 3, "X", ytdl="y", input_conf="c")
    assert "--sub-visibility=yes" in a and "--slang=en,en-US,en-GB,en-orig" in a
    assert "--ytdl-raw-options-append=write-auto-subs=" in a and "--ytdl-raw-options-append=sub-langs=en.*" in a
