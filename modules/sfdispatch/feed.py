"""SFPD dispatched-calls feed (data.sf.gov gnap-fj3t): fetch, parse, dedupe, stats."""
import os, statistics, urllib.parse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

LA = ZoneInfo("America/Los_Angeles")
DEFAULT_URL = "https://data.sf.gov/resource/gnap-fj3t.json"
WINDOW = timedelta(hours=24)
STALE_AFTER = timedelta(minutes=30)
OVERLAP = timedelta(minutes=30)  # re-read recent rows; dedupe absorbs repeats


@dataclass
class Call:
    cad: str
    received: datetime
    dispatched: "datetime | None"
    type: str
    priority: str
    place: str
    hood: str
    lon: "float | None"
    lat: "float | None"


@dataclass
class Stats:
    total: int
    unplotted: int
    top_types: list
    top_hoods: list
    median_dispatch: dict


def now_la():
    return datetime.now(LA)


def _ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.split(".")[0]).replace(tzinfo=LA)
    except ValueError:
        return None


def parse_call(raw):
    cad, received = raw.get("cad_number"), _ts(raw.get("received_datetime"))
    if not cad or received is None:
        return None
    lon = lat = None
    pt = raw.get("intersection_point") or {}
    coords = pt.get("coordinates") if isinstance(pt, dict) else None
    if coords and len(coords) == 2:
        try:
            lon, lat = float(coords[0]), float(coords[1])
        except (TypeError, ValueError):
            lon = lat = None
    pr = (raw.get("priority_final") or raw.get("priority_original") or "").upper()
    return Call(
        cad=cad, received=received, dispatched=_ts(raw.get("dispatch_datetime")),
        type=(raw.get("call_type_final_desc") or raw.get("call_type_original_desc") or "Unknown").title(),
        priority=pr if pr in ("A", "B", "C") else "?",
        place=raw.get("intersection_name") or "",
        hood=raw.get("analysis_neighborhood") or "Unknown",
        lon=lon, lat=lat,
    )


def build_url(since):
    base = os.environ.get("SFD_URL") or DEFAULT_URL
    q = {
        "$where": f"received_datetime > '{since.strftime('%Y-%m-%dT%H:%M:%S')}'",
        "$order": "received_datetime ASC",
        "$limit": "5000",
    }
    return base + "?" + urllib.parse.urlencode(q)


def requests_get_json(url):
    import requests
    r = requests.get(url, timeout=15, headers={"User-Agent": "pizero-tv"})
    r.raise_for_status()
    return r.json()


class Feed:
    def __init__(self, fetch=requests_get_json, clock=now_la):
        self.fetch, self.clock = fetch, clock
        self.calls = []
        self._seen = set()
        self._loaded = None
        self.status = "OFFLINE"
        self.data_age = None

    def poll(self):
        now = self.clock()
        since = max((c.received - OVERLAP for c in self.calls), default=now - WINDOW)
        try:
            rows = self.fetch(build_url(since))
        except Exception:
            self.status = "OFFLINE"
            return []
        new = []
        for raw in rows if isinstance(rows, list) else []:
            loaded = _ts(raw.get("data_loaded_at"))
            if loaded and (self._loaded is None or loaded > self._loaded):
                self._loaded = loaded
            c = parse_call(raw)
            if c and c.cad not in self._seen and c.received >= now - WINDOW:
                self._seen.add(c.cad)
                new.append(c)
        self.calls.extend(new)
        cutoff = now - WINDOW
        self.calls = [c for c in self.calls if c.received >= cutoff]
        self._seen = {c.cad for c in self.calls}
        self.data_age = now - self._loaded if self._loaded else None
        self.status = "LIVE" if self.data_age is not None and self.data_age <= STALE_AFTER else "STALE"
        return new


def stats(calls):
    by_pr = {}
    for c in calls:
        if c.dispatched and c.priority in ("A", "B", "C"):
            by_pr.setdefault(c.priority, []).append((c.dispatched - c.received).total_seconds())
    return Stats(
        total=len(calls),
        unplotted=sum(1 for c in calls if c.lon is None),
        top_types=Counter(c.type for c in calls).most_common(5),
        top_hoods=Counter(c.hood for c in calls if c.hood != "Unknown").most_common(5),
        median_dispatch={p: timedelta(seconds=statistics.median(v)) for p, v in by_pr.items()},
    )
