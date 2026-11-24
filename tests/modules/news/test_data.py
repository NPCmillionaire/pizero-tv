import json, os
from datetime import datetime, timezone

import pytest

from modules.news import data

D = os.path.join(os.path.dirname(__file__), "fixtures")
L = lambda n: json.load(open(os.path.join(D, n + ".json")))


def test_parse_usgs():
    q = data.parse_quakes(L("quakes"))
    assert len(q) == 51 and q == sorted(q, key=lambda x: x.time, reverse=True)
    first = q[0]
    assert first.mag == 2.5 and first.place == "40 km W of Salamatof, Alaska" and first.time.tzinfo is not None
    assert -180 <= first.lon <= 180 and first.depth_km >= -10


def test_strongest():
    q = data.parse_quakes(L("quakes"))
    s = data.strongest(q)
    assert s.mag == max(x.mag for x in q)


def test_parse_usgs_skips_null_magnitude():
    p = L("quakes")
    p["features"][0]["properties"]["mag"] = None
    assert len(data.parse_quakes(p)) == 50


def test_parse_hn_items():
    s = data.parse_hn(L("hn"))
    assert s[0].title == "Nvidia Reinstates Jensen Huang as CEO" and s[0].domain == "cnbc.com"
    assert s[0].score == 2287 and s[0].comments == 3294


def test_parse_hn_skips_dead_and_none():
    items = [None, {"id": 1, "dead": True, "title": "x", "time": 1}] + L("hn")
    assert len(data.parse_hn(items)) == len(L("hn"))


def test_ask_hn_has_no_domain():
    s = data.parse_hn([{"id": 2, "title": "Ask HN: anything?", "score": 5, "descendants": 1, "time": 1, "type": "story"}])
    assert s[0].domain == "news.ycombinator.com"


@pytest.mark.parametrize("secs,txt", [(30, "just now"), (125, "2m ago"), (3 * 3600 + 5, "3h ago"), (3 * 86400, "3d ago")])
def test_hn_age_text(secs, txt):
    assert data.ago(secs) == txt


def test_place_is_capitalized():
    p = L("quakes")
    p["features"][0]["properties"]["place"] = "west of Macquarie Island"
    assert data.parse_quakes(p)[0].place == "West of Macquarie Island"
