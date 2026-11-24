import json, os

import pytest

from modules.flights import data

FX = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "aircraft.json")))
HOME = (37.7749, -122.4194)


def test_parse_aircraft():
    ac = data.parse(FX, *HOME)
    a = next(x for x in ac if x.hex == "a524c5")
    assert a.callsign == "SKW3057" and a.reg == "N430SY" and a.type == "E75L" and a.alt == 6900
    assert a.speed == 295.0 and a.track == 328.3 and a.rate == -448
    assert abs(a.dist_nm - 54.375) < 0.5 and abs(a.bearing - 327.8) < 1.0


def test_sorted_by_distance():
    ac = data.parse(FX, *HOME)
    assert [a.dist_nm for a in ac] == sorted(a.dist_nm for a in ac)


def test_skip_no_position():
    p = {"ac": [{"hex": "abc123", "flight": "X1"}, FX["ac"][0]], "now": FX["now"]}
    assert [a.hex for a in data.parse(p, *HOME)] == [FX["ac"][0]["hex"]]


def test_ground_altitude():
    p = {"ac": [dict(FX["ac"][0], alt_baro="ground")], "now": FX["now"]}
    assert data.parse(p, *HOME)[0].alt == 0 and data.parse(p, *HOME)[0].on_ground


@pytest.mark.parametrize("lat,lon,brg", [(38.7749, -122.4194, 0), (37.7749, -121.2, 90), (36.7749, -122.4194, 180)])
def test_bearing_distance(lat, lon, brg):
    d, b = data.bearing_distance(*HOME, lat, lon)
    assert abs(b - brg) < 1 and d > 50


@pytest.mark.parametrize("cs,airline", [("UAL123", "United"), ("SKW3057", "SkyWest"), ("N123AB", None), ("", None)])
def test_airline(cs, airline):
    assert data.airline(cs) == airline


def test_type_name_known_and_unknown():
    assert data.type_name("B738") == "Boeing 737-800" and data.type_name("ZZZZ") == "ZZZZ"


def test_emergency_squawk():
    a = data.parse({"ac": [dict(FX["ac"][0], squawk="7700")], "now": FX["now"]}, *HOME)[0]
    assert a.emergency == "general emergency"
