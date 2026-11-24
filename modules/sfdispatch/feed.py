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
COLUMNS = ("cad_number", "received_datetime", "dispatch_datetime", "call_type_final_desc",
           "call_type_original_desc", "priority_final", "priority_original", "intersection_name",
           "intersection_point", "analysis_neighborhood", "data_loaded_at")
FULL_EVERY = 10   # polls between full 24 h re-reads (~10 min at 60 s polls)
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


ACRONYMS = {"DV", "DUI", "ATM", "GTA", "AMB", "SRO", "BART", "MUNI", "SFPD", "SFFD", "PD", "ID"}


def titlecase(s):
    """'FIGHT NO WEAPON DV' -> 'Fight No Weapon DV'; '01ST ST' -> '01st St'; keeps W/Weapon."""
    def word(w):
        if w.upper() in ACRONYMS:
            return w.upper()
        parts = w.split("/")
        return "/".join(p[:1].upper() + p[1:].lower() if p[:1].isalpha() else p.lower() for p in parts)
    return " ".join(word(w) for w in s.split(" "))


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
        type=titlecase(raw.get("call_type_final_desc") or raw.get("call_type_original_desc") or "Unknown"),
        priority=pr if pr in ("A", "B", "C") else "?",
        place=titlecase((raw.get("intersection_name") or "").replace("\\", "/")),
        hood=raw.get("analysis_neighborhood") or "Unknown",
        lon=lon, lat=lat,
    )


def build_url(since):
    base = os.environ.get("SFD_URL") or DEFAULT_URL
    q = {
        "$select": ",".join(COLUMNS),
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
    """Holds the last 24 h of calls keyed by CAD number.

    Most polls are incremental (recent rows only). Every FULL_EVERY polls the whole
    24 h window is re-read, which picks up calls that were dispatched late (the
    dataset only lists a call once dispatched) and rows whose fields changed.
    """

    def __init__(self, fetch=requests_get_json, clock=now_la):
        self.fetch, self.clock = fetch, clock
        self._by_cad = {}
        self._loaded = None
        self._n = 0
        self.status = "OFFLINE"
        self.data_age = None

    @property
    def calls(self):
        return sorted(self._by_cad.values(), key=lambda c: c.received)

    def poll(self):
        now = self.clock()
        cutoff = now - WINDOW
        full = self._n % FULL_EVERY == 0 or not self._by_cad
        since = cutoff if full else max(c.received for c in self._by_cad.values()) - OVERLAP
        try:
            rows = self.fetch(build_url(since))
        except Exception:
            self.status = "OFFLINE"
            return []
        self._n += 1
        new = []
        for raw in rows if isinstance(rows, list) else []:
            try:
                loaded = _ts(raw.get("data_loaded_at"))
                c = parse_call(raw)
            except Exception:   # malformed row: skip it, keep the rest
                continue
            if loaded and (self._loaded is None or loaded > self._loaded):
                self._loaded = loaded
            if c and c.received >= cutoff:
                if c.cad not in self._by_cad:
                    new.append(c)
                self._by_cad[c.cad] = c
        self._by_cad = {k: c for k, c in self._by_cad.items() if c.received >= cutoff}
        self.data_age = now - self._loaded if self._loaded else None
        self.status = "LIVE" if self.data_age is not None and self.data_age <= STALE_AFTER else "STALE"
        return sorted(new, key=lambda c: c.received)


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
