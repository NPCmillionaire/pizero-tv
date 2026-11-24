"""USGS earthquakes + Hacker News front page."""
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse


@dataclass
class Quake:
    mag: float
    place: str
    time: datetime
    lon: float
    lat: float
    depth_km: float
    tsunami: bool
    alert: str | None


@dataclass
class Story:
    title: str
    domain: str
    score: int
    comments: int
    time: int


def parse_quakes(p):
    out = []
    for f in p["features"]:
        pr, (lon, lat, depth) = f["properties"], f["geometry"]["coordinates"][:3]
        if pr.get("mag") is None:
            continue
        place = pr.get("place") or "Unknown location"
        out.append(Quake(float(pr["mag"]), place[:1].upper() + place[1:],
                         datetime.fromtimestamp(pr["time"] / 1000, timezone.utc), float(lon), float(lat),
                         float(depth or 0), bool(pr.get("tsunami")), pr.get("alert")))
    return sorted(out, key=lambda q: q.time, reverse=True)


def strongest(quakes):
    return max(quakes, key=lambda q: (q.mag, q.time)) if quakes else None


def parse_hn(items):
    out = []
    for it in items:
        if not isinstance(it, dict) or it.get("dead") or it.get("deleted") or not it.get("title"):
            continue
        host = urlparse(it.get("url") or "").netloc.lower()
        out.append(Story(it["title"], host[4:] if host.startswith("www.") else (host or "news.ycombinator.com"),
                         int(it.get("score") or 0), int(it.get("descendants") or 0), int(it.get("time") or 0)))
    if not out:
        raise ValueError("no stories")
    return out


def ago(secs):
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"
