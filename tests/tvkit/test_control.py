import os
import tempfile
import threading

from tvkit import control


def test_control_roundtrip():
    path = os.path.join(tempfile.mkdtemp(), "t.sock")
    srv = control.Server(path)
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            srv.poll(lambda line: '{"module": "aa"}' if line == "status" else "?")
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    try:
        assert control.send(path, "status") == '{"module": "aa"}'
    finally:
        stop.set()
        t.join(1)
        srv.close()


def test_send_missing_socket_raises():
    import pytest
    with pytest.raises(control.NotRunning):
        control.send("/tmp/definitely-not-here.sock", "status")
