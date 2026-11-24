import json, os
from datetime import datetime

import pytest

from modules.weather import data

FX = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "forecast.json")))
ALL_WMO = [0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77,
           80, 81, 82, 85, 86, 95, 96, 99]


def test_parse_current():
    w = data.parse(FX)
    assert w.temp == 49.4 and w.feels == 45.0 and w.humidity == 72 and w.code == 0
    assert w.wind == 5.1 and w.wind_dir == 130 and w.gust == 5.8 and w.is_day is False
    assert w.now == datetime(2026, 11, 23, 20, 0)


def test_parse_daily_7():
    w = data.parse(FX)
    assert len(w.days) == 7 and w.days[0].date.isoformat() == "2026-11-23"
    assert w.days[0].sunrise == datetime(2026, 11, 23, 6, 58)
    assert all(d.hi >= d.lo for d in w.days)


def test_parse_hourly_25():
    w = data.parse(FX)
    assert len(w.hours) == 25 and w.hours[0].time == datetime(2026, 11, 23, 20, 0)


def test_parse_garbage_raises():
    with pytest.raises((KeyError, TypeError, ValueError)):
        data.parse({"error": True, "reason": "bad"})


@pytest.mark.parametrize("code", ALL_WMO)
def test_wmo_icon_mapping_total(code):
    text, icon = data.condition(code)
    assert text and icon in data.ICONS


def test_unknown_wmo_code_is_honest():
    assert data.condition(1234) == ("Unknown conditions", "cloud")


@pytest.mark.parametrize("now,expect", [
    (datetime(2026, 11, 23, 6, 0), None),            # before sunrise
    (datetime(2026, 11, 23, 6, 58), 0.0),
    (datetime(2026, 11, 23, 12, 0), 0.5),
    (datetime(2026, 11, 23, 17, 2), 1.0),
    (datetime(2026, 11, 23, 20, 0), None),           # after sunset
])
def test_sun_position_fraction(now, expect):
    f = data.sun_fraction(now, datetime(2026, 11, 23, 6, 58), datetime(2026, 11, 23, 17, 2))
    assert (f is None and expect is None) or abs(f - expect) < 0.01


@pytest.mark.parametrize("deg,name", [(0, "N"), (130, "SE"), (270, "W"), (350, "N"), (200, "SSW")])
def test_compass(deg, name):
    assert data.compass(deg) == name


def test_outlook_mentions_rain_when_likely():
    w = data.parse(FX)
    for h in w.hours[3:6]:
        h.pop, h.code = 70, 61
    s = data.outlook(w)
    assert "rain" in s.lower() and "70%" in s


def test_outlook_quiet_when_dry():
    w = data.parse(FX)
    for h in w.hours:
        h.pop = 0
    assert data.outlook(w) is None
