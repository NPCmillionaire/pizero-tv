import json, os

import pytest

from modules.lanradar import data

FX = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "lan.json")))

IP_NEIGH = json.dumps([
    {"dst": "192.168.1.1", "dev": "wlan0", "lladdr": "94:83:c4:00:00:01", "state": ["REACHABLE"]},
    {"dst": "192.168.1.60", "dev": "wlan0", "state": ["FAILED"]},
    {"dst": "fe80::1", "dev": "wlan0", "lladdr": "94:83:c4:00:00:01", "router": None, "state": ["STALE"]},
    {"dst": "192.168.1.31", "dev": "wlan0", "lladdr": "3c:2e:f9:00:00:31", "state": ["STALE"]},
])


def test_parse_ip_neigh_json():
    rows = data.parse_ip_neigh(IP_NEIGH)
    assert [r["ip"] for r in rows] == ["192.168.1.1", "192.168.1.31"]      # IPv4 with a MAC only
    assert rows[0]["mac"] == "94:83:c4:00:00:01" and rows[0]["state"] == "REACHABLE"


@pytest.mark.parametrize("mac,vendor", [("b8:27:eb:12:34:56", "Raspberry Pi Foundation"),
                                        ("3C:2E:F9:00:00:31", "Apple"),
                                        ("da:a1:19:00:00:44", "Private address"),
                                        ("00:00:5e:00:00:01", None)])
def test_oui_lookup(mac, vendor):
    v = data.vendor(mac)
    assert v == vendor or (vendor is None and v is not None and v != "Private address")


def test_parse_devices_drops_failed_and_sorts_by_ip():
    devs = data.parse_devices(FX, known={})
    assert [d.ip for d in devs] == ["192.168.1.1", "192.168.1.20", "192.168.1.31", "192.168.1.44", "192.168.1.52"]
    assert devs[1].label == "pi.lan" and devs[2].label == "Apple device"


def test_new_device_flag():
    known = {"94:83:c4:00:00:01": 1000.0}
    devs = data.parse_devices(FX, known=known, now=1000.0 + 86400 * 3)
    by = {d.mac: d for d in devs}
    assert by["94:83:c4:00:00:01"].new is False and by["b8:27:eb:00:00:20"].new is True
    assert known["b8:27:eb:00:00:20"] == 1000.0 + 86400 * 3     # remembered from now on


def test_hosts_in_subnet():
    h = data.hosts("192.168.1.0/30")
    assert h == ["192.168.1.1", "192.168.1.2"]
    with pytest.raises(ValueError):
        data.hosts("192.168.0.0/16")          # refuse to sweep huge networks


def test_first_scan_marks_nothing_new():
    devs = data.parse_devices(FX, known={}, now=5000.0)
    assert not any(d.new for d in devs)


def test_device_new_only_for_a_day():
    known = {}
    data.parse_devices(FX[:1], known=known, now=1000.0)              # first scan primes the table
    later = data.parse_devices(FX[:2], known=known, now=2000.0)
    assert [d.new for d in later] == [False, True]
    much_later = data.parse_devices(FX[:2], known=known, now=2000.0 + 86400 + 1)
    assert [d.new for d in much_later] == [False, False]
