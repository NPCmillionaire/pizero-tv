import json, os

import pytest

from modules.space import data

D = os.path.join(os.path.dirname(__file__), "fixtures")
L = lambda n: json.load(open(os.path.join(D, n + ".json")))


def test_parse_iss():
    i = data.parse_iss(L("iss"))
    assert abs(i.lat - 35.287) < 0.01 and abs(i.lon - 134.478) < 0.01
    assert round(i.alt_km) == 416 and round(i.speed_kmh) == 27609 and i.daylight is True
    assert abs(i.sun_lat + 20.54) < 0.01 and abs(i.sun_lon - 112.08) < 0.01


def test_parse_kp_latest_and_storm_scale():
    k = data.parse_kp(L("kp"))
    assert k[-1].kp == max((x for x in k if x.time == k[-1].time), key=lambda x: x.kp).kp
    assert data.storm_level(0.67) == ("quiet", None) and data.storm_level(5.0)[1] == "G1"
    assert data.storm_level(9.0)[1] == "G5" and data.storm_level(4.3)[0] == "active"


def test_parse_wind_latest_active():
    w = data.parse_wind(L("wind"))
    assert w.speed == 315.0 and w.density == 0.98 and len(w.series) > 10


def test_parse_wind_skips_null_speeds():
    rows = [dict(L("wind")[0], proton_speed=None)] + L("wind")
    assert data.parse_wind(rows).speed == 315.0


def test_parse_neo_closest():
    n = data.parse_neo(L("neo"))
    assert n == sorted(n, key=lambda a: a.miss_km)
    assert n[0].lunar > 0 and n[0].dia_min < n[0].dia_max and n[0].name


def test_terminator_points():
    sun_lat, sun_lon = -20.5, 112.0
    assert not data.is_night(sun_lat, sun_lon, sun_lat, sun_lon)
    assert data.is_night(-sun_lat, sun_lon - 180, sun_lat, sun_lon)
    pts = data.terminator(sun_lat, sun_lon, step=10)
    assert len(pts) == 37 and all(-90 <= lat <= 90 for _, lat in pts)


@pytest.mark.parametrize("lat,lon,where", [(39.8, -98.6, "United States of America"), (0, -150, "the Pacific Ocean"),
                                           (30, -40, "the Atlantic Ocean"), (-20, 80, "the Indian Ocean")])
def test_where(lat, lon, where):
    assert data.where(lat, lon) == where
