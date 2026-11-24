"""~/.config/pizero-tv/config.toml — per-Pi settings that never go in the repo."""
import os, sys, tomllib
from dataclasses import dataclass, field

DEFAULT_PATH = os.path.expanduser("~/.config/pizero-tv/config.toml")


@dataclass
class Place:
    name: str
    lat: float
    lon: float
    timezone: str | None = None


@dataclass
class Config:
    place: Place | None = None
    units_temp: str = "F"
    lan_subnet: str | None = None
    cycle_seconds: int = 90
    cycle_modules: list | None = None
    raw: dict = field(default_factory=dict)


def load(path=None):
    path = path or DEFAULT_PATH
    try:
        with open(path, "rb") as fh:
            d = tomllib.load(fh)
    except FileNotFoundError:
        return Config()
    except Exception as e:
        print(f"config: ignoring {path}: {e}", file=sys.stderr)
        return Config()
    def sec(name):
        v = d.get(name)
        return v if isinstance(v, dict) else {}

    p = sec("place")
    place = None
    try:
        if "lat" in p and "lon" in p:
            place = Place(str(p.get("name", "Here")), float(p["lat"]), float(p["lon"]), p.get("timezone"))
    except (TypeError, ValueError) as e:
        print(f"config: ignoring [place]: {e}", file=sys.stderr)
    try:
        seconds = max(10, int(sec("cycle").get("seconds", 90)))
    except (TypeError, ValueError):
        print("config: [cycle] seconds must be a number; using 90", file=sys.stderr)
        seconds = 90
    mods = sec("cycle").get("modules")
    return Config(
        place=place,
        units_temp=str(sec("units").get("temp", "F")).upper(),
        lan_subnet=sec("lan").get("subnet") if isinstance(sec("lan").get("subnet"), str) else None,
        cycle_seconds=seconds,
        cycle_modules=[str(m) for m in mods] if isinstance(mods, list) else None,
        raw=d,
    )
