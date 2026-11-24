from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from modules.sfdispatch import feed
from modules.sfdispatch.feed import Feed, build_url, parse_call, stats

LA = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 11, 23, 18, 55, 0, tzinfo=LA)

SAMPLE = {
    "cad_number": "263272725", "received_datetime": "2026-11-23T18:40:53.000",
    "dispatch_datetime": "2026-11-23T18:42:32.000",
    "call_type_final_desc": "TRAF VIOLATION CITE", "priority_final": "C",
    "intersection_name": "SUTTER ST \\ VAN NESS AVE",
    "intersection_point": {"type": "Point", "coordinates": [-122.421758104, 37.78754814]},
    "analysis_neighborhood": "Nob Hill", "police_district": "NORTHERN",
    "data_loaded_at": "2026-11-23T18:45:00.000",
}


def rec(cad, received, **kw):
    r = dict(SAMPLE, cad_number=cad, received_datetime=received.strftime("%Y-%m-%dT%H:%M:%S.000"))
    r.update(kw)
    return r


def test_parse_basic():
    c = parse_call(SAMPLE)
    assert c.cad == "263272725"
    assert c.lon == -122.421758104 and c.lat == 37.78754814
    assert c.received == datetime(2026, 11, 23, 18, 40, 53, tzinfo=LA)
    assert c.received.tzinfo == LA
    assert c.dispatched - c.received == timedelta(seconds=99)
    assert c.type == "Traffic Violation Cite"
    assert c.priority == "C" and c.hood == "Nob Hill"
    assert c.place == "Sutter St / Van Ness Ave"


def test_parse_no_location():
    r = dict(SAMPLE)
    del r["intersection_point"]
    c = parse_call(r)
    assert c is not None and c.lon is None and c.lat is None


def test_parse_missing_required():
    r = dict(SAMPLE)
    del r["cad_number"]
    assert parse_call(r) is None


def test_parse_unknown_priority():
    assert parse_call(dict(SAMPLE, priority_final="E")).priority == "?"


def test_build_url(monkeypatch):
    monkeypatch.delenv("SFD_URL", raising=False)
    u = build_url(NOW - timedelta(hours=24))
    assert u.startswith("https://data.sf.gov/resource/gnap-fj3t.json?")
    assert "%24limit=5000" in u
    assert "received_datetime+ASC" in u or "received_datetime%20ASC" in u
    assert "2026-11-22T18%3A55%3A00" in u


def test_build_url_env_override(monkeypatch):
    monkeypatch.setenv("SFD_URL", "http://127.0.0.1:9/x.json")
    assert build_url(NOW).startswith("http://127.0.0.1:9/x.json?")


def make_feed(pages):
    """pages: list of record lists or Exception instances, one per poll."""
    it = iter(pages)

    def fetch(url):
        p = next(it)
        if isinstance(p, Exception):
            raise p
        return p
    return Feed(fetch=fetch, clock=lambda: NOW)


def test_dedupe():
    f = make_feed([[SAMPLE], [SAMPLE]])
    assert len(f.poll()) == 1
    assert f.poll() == []
    assert len(f.calls) == 1


def test_prune_24h():
    old = rec("1", NOW - timedelta(hours=25))
    new = rec("2", NOW - timedelta(hours=1))
    f = make_feed([[old, new]])
    f.poll()
    assert [c.cad for c in f.calls] == ["2"]


def test_poll_failure_sets_offline():
    f = make_feed([[SAMPLE], ConnectionError("down")])
    f.poll()
    assert f.status == "LIVE"
    assert f.poll() == []
    assert f.status == "OFFLINE"
    assert len(f.calls) == 1


def test_offline_before_first_success():
    f = make_feed([ConnectionError("down")])
    assert f.poll() == [] and f.status == "OFFLINE" and f.calls == []


@pytest.mark.parametrize("age_min,status", [(10, "LIVE"), (45, "STALE")])
def test_staleness(age_min, status):
    loaded = (NOW - timedelta(minutes=age_min)).strftime("%Y-%m-%dT%H:%M:%S.000")
    f = make_feed([[rec("1", NOW - timedelta(minutes=50), data_loaded_at=loaded)]])
    f.poll()
    assert f.status == status
    assert f.data_age == timedelta(minutes=age_min)


def test_empty_page_keeps_status_from_age():
    f = make_feed([[]])
    f.poll()
    assert f.status == "STALE"   # reachable but we have no evidence of fresh data


def test_stats():
    t = NOW - timedelta(hours=1)
    calls = [parse_call(rec(str(i), t, priority_final="A",
                            dispatch_datetime=(t + timedelta(seconds=s)).strftime("%Y-%m-%dT%H:%M:%S.000")))
             for i, s in enumerate((60, 120, 600))]
    nl = dict(rec("9", t), analysis_neighborhood="Mission")
    del nl["intersection_point"]
    del nl["dispatch_datetime"]
    calls.append(parse_call(nl))
    s = stats(calls)
    assert s.total == 4
    assert s.unplotted == 1
    assert s.median_dispatch["A"] == timedelta(seconds=120)
    assert "C" not in s.median_dispatch
    assert s.top_hoods[0] == ("Nob Hill", 3)
    assert s.top_types[0] == ("Traffic Violation Cite", 4)


def test_incremental_poll_overlaps_30min():
    urls = []

    def fetch(url):
        urls.append(url)
        return [SAMPLE]
    f = Feed(fetch=fetch, clock=lambda: NOW)
    f.poll()
    f.poll()
    # max received 18:40:53 minus 30 min overlap
    assert "2026-11-23T18%3A10%3A53" in urls[1]


def test_top_hoods_excludes_unknown():
    t = NOW - timedelta(hours=1)
    calls = [parse_call(rec(str(i), t, analysis_neighborhood=None)) for i in range(5)]
    calls.append(parse_call(rec("x", t)))
    assert stats(calls).top_hoods == [("Nob Hill", 1)]


def test_titlecase_keeps_acronyms_and_ordinals():
    from modules.sfdispatch.feed import titlecase
    assert titlecase("FIGHT NO WEAPON DV") == "Fight No Weapon DV"
    assert titlecase("01ST ST \\ LANSING ST") == "01st St \\ Lansing St"
    assert titlecase("FIGHT W/WEAPON") == "Fight W/Weapon"


def test_build_url_selects_only_needed_columns(monkeypatch):
    monkeypatch.delenv("SFD_URL", raising=False)
    from urllib.parse import parse_qs, urlparse
    q = parse_qs(urlparse(build_url(NOW)).query)
    cols = set(q["$select"][0].split(","))
    assert cols == {"cad_number", "received_datetime", "dispatch_datetime", "call_type_final_desc",
                    "call_type_original_desc", "priority_final", "priority_original",
                    "intersection_name", "intersection_point", "analysis_neighborhood",
                    "data_loaded_at"}


def test_full_refresh_recovers_late_dispatched_call():
    """A call received 2h before the newest one only appears later (late dispatch)."""
    newest = rec("n", NOW - timedelta(minutes=10))
    late = rec("late", NOW - timedelta(hours=2, minutes=10))
    urls = []
    pages = iter([[newest]] + [[]] * (feed.FULL_EVERY - 1) + [[newest, late]])

    def fetch(url):
        urls.append(url)
        return next(pages)
    f = Feed(fetch=fetch, clock=lambda: NOW)
    for _ in range(feed.FULL_EVERY):
        f.poll()
    got = f.poll()
    assert [c.cad for c in got] == ["late"]
    assert "2026-11-22T18%3A55%3A00" in urls[-1]   # full 24h window


def test_updated_row_replaces_stored_call():
    first = dict(SAMPLE)
    del first["dispatch_datetime"]
    f = make_feed([[first], [SAMPLE]])
    f.poll()
    assert f.poll() == []                       # not re-announced
    assert len(f.calls) == 1 and f.calls[0].dispatched is not None


def test_malformed_rows_are_skipped():
    bad = [42, None, dict(SAMPLE, cad_number="x", priority_final=7, call_type_final_desc=9), SAMPLE]
    f = make_feed([bad])
    got = f.poll()
    assert [c.cad for c in got] == ["263272725"]
    assert f.status == "LIVE"


def test_next_url_then_ingest_matches_poll():
    f = Feed(fetch=None, clock=lambda: NOW)
    url = f.next_url()
    assert "2026-11-22T18%3A55%3A00" in url          # first read: full 24 h window
    got = f.ingest([SAMPLE])
    assert [c.cad for c in got] == ["263272725"] and f.status == "LIVE"
    assert "2026-11-23T18%3A10%3A53" in f.next_url()  # incremental, 30 min overlap


def test_ingest_garbage_payload_raises_for_source():
    f = Feed(fetch=None, clock=lambda: NOW)
    with pytest.raises(ValueError):
        f.ingest("<html>")


def test_call_types_expand_sfpd_abbreviations():
    from modules.sfdispatch.feed import titlecase
    assert parse_call(dict(SAMPLE, call_type_final_desc="TRAF VIOLATION CITE")).type == "Traffic Violation Cite"
    assert parse_call(dict(SAMPLE, call_type_final_desc="COMPLAINT UNKN")).type == "Complaint Unknown"
    assert parse_call(dict(SAMPLE, call_type_final_desc="INJURY VEH ACCIDENT")).type == "Injury Vehicle Accident"
    assert parse_call(dict(SAMPLE, call_type_final_desc="PERSON W/KNIFE")).type == "Person with Knife"
    assert titlecase("01ST ST") == "01st St"     # streets are not expanded
