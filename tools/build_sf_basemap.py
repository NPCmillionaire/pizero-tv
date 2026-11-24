#!/usr/bin/env python3
"""Build modules/sfdispatch/basemap.json from OSM (Overpass) + SF neighborhoods.

Run on a dev machine, not the Pi:  python3 tools/build_sf_basemap.py
"""
import json, math, os, sys

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "modules", "sfdispatch"))
from geo import BBOX  # noqa: E402

OUT = os.path.join(ROOT, "modules", "sfdispatch", "basemap.json")
OVERPASS = "https://overpass-api.de/api/interpreter"
HOODS = "https://data.sf.gov/resource/j2bu-swwd.geojson?$limit=100"
CLASS = {"motorway": "motorway", "trunk": "primary", "primary": "primary",
         "secondary": "secondary"}
MIN_STEP_M = 15


def get(url, data=None):
    hdr = {"User-Agent": "pizero-tv-basemap"}
    r = requests.post(url, data=data, headers=hdr, timeout=180) if data else \
        requests.get(url, headers=hdr, timeout=180)
    r.raise_for_status()
    return r.json()


def simplify(pts):
    """Drop points closer than MIN_STEP_M to the last kept one; round to 5 dp."""
    if not pts:
        return []
    kx = 111320 * math.cos(math.radians(37.76))
    out = [pts[0]]
    for p in pts[1:-1]:
        q = out[-1]
        if math.hypot((p[0] - q[0]) * kx, (p[1] - q[1]) * 110540) >= MIN_STEP_M:
            out.append(p)
    if len(pts) > 1:
        out.append(pts[-1])
    return [[round(x, 5), round(y, 5)] for x, y in out]


def roads():
    s, w, n, e = BBOX[1], BBOX[0], BBOX[3], BBOX[2]
    q = (f'[out:json][timeout:120];way["highway"~"^(motorway|trunk|primary|secondary)$"]'
         f'({s},{w},{n},{e});out geom;')
    data = get(OVERPASS, {"data": q})
    res = {"motorway": [], "primary": [], "secondary": []}
    for el in data["elements"]:
        cls = CLASS.get(el.get("tags", {}).get("highway"))
        geom = el.get("geometry")
        if cls and geom:
            line = simplify([(g["lon"], g["lat"]) for g in geom])
            if len(line) >= 2:
                res[cls].append(line)
    return res


def hoods():
    out = []
    for f in get(HOODS)["features"]:
        rings = [simplify(ring) for poly in f["geometry"]["coordinates"] for ring in poly[:1]]
        out.append({"name": f["properties"]["nhood"], "rings": [r for r in rings if len(r) >= 3]})
    return out


def main():
    data = {"bbox": list(BBOX), "roads": roads(), "hoods": hoods()}
    with open(OUT, "w") as fh:
        json.dump(data, fh, separators=(",", ":"))
    print(f"wrote {OUT} ({os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    main()
