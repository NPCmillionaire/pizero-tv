import os

import pytest

from tvkit import cli, control

FAKE = os.path.join(os.path.dirname(__file__), "fakemods")


@pytest.fixture
def reg():
    from tvkit import registry
    return registry.discover(FAKE, package="tests.fakemods")


def test_cli_module_name_maps_to_show(reg):
    assert cli.to_command(["alpha"], reg) == "show alpha"
    assert cli.to_command(["a"], reg) == "show alpha"         # alias
    assert cli.to_command(["cycle", "45", "beta"], reg) == "cycle 45 beta"
    assert cli.to_command([], reg) == "status"


def test_cli_remote_builds_ssh_argv():
    assert cli.remote_argv("pizero", ["weather"]) == [
        "ssh", "-o", "ConnectTimeout=10", "pizero", "~/pizero-tv/bin/tv", "weather"]


def test_cli_remote_quotes_args():
    assert cli.remote_argv("pi", ["screenshot", "/tmp/a b.png"])[-1] == "'/tmp/a b.png'"


def test_cli_unknown_module_lists_choices(reg):
    with pytest.raises(cli.Usage) as e:
        cli.to_command(["omega"], reg)
    assert "alpha" in str(e.value) and "beta" in str(e.value)


def test_cli_host_not_running_message(reg, monkeypatch, capsys):
    def nope(path, line, timeout=10):
        raise control.NotRunning("x")
    monkeypatch.setattr(control, "send", nope)
    assert cli.main(["alpha"], reg=reg) == 2
    assert "tvd isn't running" in capsys.readouterr().err


def test_cli_status_pretty(reg, monkeypatch, capsys):
    monkeypatch.setattr(control, "send", lambda p, l, timeout=10:
                        '{"mode": "cycle", "phase": "module", "module": "alpha", "since_s": 12.0,'
                        ' "cycle_seconds": 90, "cycle_names": null, "data": "live", "data_age_s": null}')
    assert cli.main([], reg=reg) == 0
    out = capsys.readouterr().out
    assert "alpha" in out and "cycling every 90 s" in out


def test_cli_up_down_numbers(reg):
    assert cli.to_command(["up"], reg) == "up" and cli.to_command(["down"], reg) == "down"
    assert cli.to_command(["7"], reg) == "ch 7" and cli.to_command(["ch", "12"], reg) == "ch 12"


def test_cli_digit_passthrough(reg):
    assert cli.to_command(["digit", "4"], reg) == "digit 4"


def test_cli_does_not_import_modules_for_remote_keys(monkeypatch):
    from tvkit import registry
    monkeypatch.setattr(registry, "discover", lambda *a, **k: (_ for _ in ()).throw(AssertionError("imported")))
    sent = []
    monkeypatch.setattr(control, "send", lambda p, l, timeout=10: sent.append(l) or "ok")
    for args in (["up"], ["digit", "3"], ["7"], ["weather"], ["next"]):
        assert cli.main(args) == 0
    assert sent == ["up", "digit 3", "ch 7", "show weather", "next"]


def test_start_uses_the_systemd_service_when_installed(monkeypatch, tmp_path):
    from tvkit import cli
    unit = tmp_path / "pizero-tv.service"
    unit.write_text("[Service]\n")
    calls = []
    monkeypatch.setattr(cli, "UNIT", str(unit))
    monkeypatch.setattr(cli.subprocess, "call", lambda argv, **k: calls.append(argv) or 0)
    monkeypatch.setattr(cli.subprocess, "Popen", lambda *a, **k: calls.append("popen"))
    assert cli._start() == 0
    assert calls == [["systemctl", "--user", "start", "pizero-tv.service"]]


def test_service_restarts_forever_outside_any_ssh_session():
    import configparser, os
    p = configparser.ConfigParser(strict=False, interpolation=None)
    p.read(os.path.join(os.path.dirname(__file__), "..", "systemd", "pizero-tv.service"))
    assert p["Service"]["Restart"] == "always"
    assert p["Unit"]["StartLimitIntervalSec"] == "0"
    assert p["Install"]["WantedBy"] == "default.target"
