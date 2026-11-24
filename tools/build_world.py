#!/usr/bin/env python3
"""Build tvkit/world.json from Natural Earth 1:110m admin-0 countries (public domain).

    python3 tools/build_world.py [path/to/ne_110m_admin_0_countries.geojson]
"""
import json, os, sys

import requests

URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
       "ne_110m_admin_0_countries.geojson")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tvkit", "world.json")


def main(src=None):
    d = json.load(open(src)) if src else requests.get(URL, timeout=60).json()
    countries = []
    for f in d["features"]:
        p, g = f["properties"], f["geometry"]
        iso = p["ISO_A2_EH"] if p.get("ISO_A2", "-99") == "-99" else p["ISO_A2"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        rings = [[[round(x, 2), round(y, 2)] for x, y in poly[0]] for poly in polys]
        countries.append({"iso": iso, "name": p["NAME"], "label": [round(p["LABEL_X"], 2), round(p["LABEL_Y"], 2)],
                          "rings": rings})
    json.dump({"source": "Natural Earth 1:110m admin-0 countries", "countries": countries},
              open(OUT, "w"), separators=(",", ":"))
    print(f"wrote {OUT} ({os.path.getsize(OUT) // 1024} KB, {len(countries)} countries)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
