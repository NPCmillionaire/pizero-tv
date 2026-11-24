"""ISS position, NOAA space weather and NASA near-Earth asteroids."""
import math
from dataclasses import dataclass
from datetime import datetime

from tvkit import world


@dataclass
class ISS:
    lat: float
    lon: float
    alt_km: float
    speed_kmh: float
    daylight: bool
    ts: int
    sun_lat: float
    sun_lon: float


@dataclass
class Kp:
    time: datetime
    kp: float


@dataclass
class Wind:
    speed: float
    density: float | None
    series: list


@dataclass
class Asteroid:
    name: str
    miss_km: float
    lunar: float
    dia_min: float
    dia_max: float
    speed_kms: float
    hazardous: bool
    when: str


def parse_iss(p):
    return ISS(float(p["latitude"]), float(p["longitude"]), float(p["altitude"]), float(p["velocity"]),
               p.get("visibility") == "daylight", int(p["timestamp"]), float(p["solar_lat"]), float(p["solar_lon"]))


def parse_kp(p):
    out = [Kp(datetime.fromisoformat(r["time_tag"]), float(r["Kp"])) for r in p if isinstance(r, dict) and "Kp" in r]
    if not out:
        raise ValueError("no Kp readings")
    return sorted(out, key=lambda k: k.time)


def storm_level(kp):
    if kp < 4:
        return "quiet", None
    if kp < 5:
        return "active", None
    g = min(5, int(kp) - 4)
    return ["minor storm", "moderate storm", "strong storm", "severe storm", "extreme storm"][g - 1], f"G{g}"


def parse_wind(p):
    rows = [r for r in p if r.get("proton_speed") is not None and r.get("active", True)]
    if not rows:
        raise ValueError("no solar wind readings")
    rows.sort(key=lambda r: r["time_tag"])
    last = rows[-1]
    return Wind(float(last["proton_speed"]), last.get("proton_density"), [float(r["proton_speed"]) for r in rows])


def parse_neo(p):
    out = []
    for day in p["near_earth_objects"].values():
        for a in day:
            ca = a["close_approach_data"][0]
            d = a["estimated_diameter"]["meters"]
            out.append(Asteroid(a["name"].strip("()"), float(ca["miss_distance"]["kilometers"]),
                                float(ca["miss_distance"]["lunar"]), float(d["estimated_diameter_min"]),
                                float(d["estimated_diameter_max"]),
                                float(ca["relative_velocity"]["kilometers_per_second"]),
                                bool(a["is_potentially_hazardous_asteroid"]), ca.get("close_approach_date_full", "")))
    if not out:
        raise ValueError("no asteroids")
    return sorted(out, key=lambda a: a.miss_km)


def is_night(lat, lon, sun_lat, sun_lon):
    """True when the sun is below the horizon at (lat, lon)."""
    p1, p2 = math.radians(lat), math.radians(sun_lat)
    dl = math.radians(lon - sun_lon)
    return math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(dl) < 0


def terminator(sun_lat, sun_lon, step=2):
    """Day/night boundary as (lon, lat) points from -180 to 180."""
    t = math.tan(math.radians(sun_lat)) or 1e-9
    pts = []
    for lon in range(-180, 181, step):
        lat = math.degrees(math.atan(-math.cos(math.radians(lon - sun_lon)) / t))
        pts.append((lon, lat))
    return pts


def _inside(lon, lat, ring):
    inside, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def _ocean(lat, lon):
    if lat > 66:
        return "the Arctic Ocean"
    if lat < -60:
        return "the Southern Ocean"
    if -70 <= lon <= 20:
        return "the Atlantic Ocean"
    if 20 < lon <= 120 and lat < 25 or 120 < lon <= 146 and lat < -10:
        return "the Indian Ocean"
    return "the Pacific Ocean"


def where(lat, lon):
    for c in world.countries():
        if any(_inside(lon, lat, ring) for ring in c["rings"]):
            return c["name"]
    return _ocean(lat, lon)
