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
    p = d.get("place") or {}
    place = None
    if "lat" in p and "lon" in p:
        place = Place(str(p.get("name", "Here")), float(p["lat"]), float(p["lon"]), p.get("timezone"))
    return Config(
        place=place,
        units_temp=str((d.get("units") or {}).get("temp", "F")).upper(),
        lan_subnet=(d.get("lan") or {}).get("subnet"),
        cycle_seconds=int((d.get("cycle") or {}).get("seconds", 90)),
        cycle_modules=(d.get("cycle") or {}).get("modules"),
        raw=d,
    )
