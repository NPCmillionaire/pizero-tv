#!/usr/bin/env python3
"""Build modules/lanradar/oui.tsv.gz (MAC prefix → short vendor name) from the IEEE MA-L registry."""
import csv, gzip, io, os, re

import requests

URL = "https://standards-oui.ieee.org/oui/oui.csv"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "modules", "lanradar", "oui.tsv.gz")
DROP = re.compile(r"[,.]?\s+(inc|incorporated|corp|corporation|co|company|ltd|limited|llc|gmbh|ag|sa|s\.a|"
                  r"b\.v|bv|oy|ab|plc|technologies|technology|electronics|international|group|holdings)\b.*$", re.I)


def short(name):
    n = DROP.sub("", name.strip()).strip(" ,.")
    return n or name.strip()


def main():
    text = requests.get(URL, timeout=120, headers={"User-Agent": "pizero-tv oui build"}).text
    rows = sorted({(r["Assignment"].upper(), short(r["Organization Name"])) for r in csv.DictReader(io.StringIO(text))})
    with gzip.open(OUT, "wt") as fh:
        for prefix, org in rows:
            fh.write(f"{prefix}\t{org}\n")
    print(f"wrote {OUT}: {len(rows)} prefixes, {os.path.getsize(OUT) // 1024} KB")


if __name__ == "__main__":
    main()
