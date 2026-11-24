#!/usr/bin/env python3
"""Save a real API response as a test fixture:  capture_fixture.py URL OUT.json [--max-items N]"""
import argparse, json, os

import requests

ap = argparse.ArgumentParser()
ap.add_argument("url")
ap.add_argument("out")
ap.add_argument("--max-items", type=int, help="truncate a top-level list")
a = ap.parse_args()
r = requests.get(a.url, timeout=30, headers={"User-Agent": "Mozilla/5.0 pizero-tv fixture"})
r.raise_for_status()
data = r.json()
if a.max_items and isinstance(data, list):
    data = data[: a.max_items]
os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
with open(a.out, "w") as fh:
    json.dump(data, fh, separators=(",", ":"))
print(f"{a.out}: {os.path.getsize(a.out) // 1024} KB")
