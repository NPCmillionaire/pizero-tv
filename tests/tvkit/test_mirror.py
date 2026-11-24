import socket, time

import pytest

from tvkit import mirror


def test_frames_survive_any_chunking():
    data = mirror.frame("H", {"host": "darwin", "cols": 90, "rows": 30}) + mirror.frame("D", b"hello")
    d = mirror.Decoder()
    got = []
    for i in range(len(data)):
        got += d.feed(data[i:i + 1])
    assert [k for k, _ in got] == ["H", "D"] and got[1][1] == b"hello"


def test_bad_frames_are_refused():
    with pytest.raises(ValueError):
        mirror.Decoder().feed(b"X\x00\x00\x00\x01a")


def test_server_builds_a_screen(tmp_path):
    pytest.importorskip("pyte")
    import tempfile, os
    d = tempfile.mkdtemp(prefix="tvm", dir="/tmp")         # AF_UNIX paths must be short on macOS
    srv = mirror.Server(os.path.join(d, "m.sock"))
    cli = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    cli.connect(srv.path)
    cli.sendall(mirror.frame("H", {"host": "darwin", "cols": 40, "rows": 10}) + mirror.frame("D", b"$ ls\r\nfiles\r\n"))
    events = []
    for _ in range(50):
        e = srv.poll()
        if e:
            events.append(e)
        if srv.session and srv.session.version >= 2:
            break
        time.sleep(0.01)
    assert events[0] == "connected"
    s = srv.session
    assert s.host == "darwin" and s.cols == 40 and s.screen.display[0].startswith("$ ls") and "files" in s.screen.display[1]
    cli.close()
    for _ in range(50):
        if srv.poll() == "disconnected":
            break
        time.sleep(0.01)
    assert srv.conn is None
    srv.close()
