#!/usr/bin/env python3
"""Rebuild tvkit/fonts/ (dev machine only).

Downloads the OFL families from github.com/google/fonts, cuts static Big Shoulders
Display weights from the variable font, and subsets Droid Sans Fallback (Apache-2.0,
copy it from a Raspberry Pi OS box: /usr/share/fonts/truetype/droid/) to katakana.

    python3 tools/build_fonts.py /path/to/DroidSansFallbackFull.ttf
"""
import io, os, sys

import requests
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tvkit", "fonts")
GF = "https://github.com/google/fonts/raw/main/ofl/"
STATIC = {
    "IBMPlexSansCondensed-Regular.ttf": "ibmplexsanscondensed/",
    "IBMPlexSansCondensed-Medium.ttf": "ibmplexsanscondensed/",
    "IBMPlexSansCondensed-SemiBold.ttf": "ibmplexsanscondensed/",
    "IBMPlexMono-Regular.ttf": "ibmplexmono/",
    "IBMPlexMono-Medium.ttf": "ibmplexmono/",
}
BIG = "bigshouldersdisplay/BigShouldersDisplay%5Bwght%5D.ttf"
KANA = ("U+0020-007E,U+30A0-30FF,U+FF66-FF9D")


def get(path):
    r = requests.get(GF + path, timeout=60)
    r.raise_for_status()
    return r.content


def main(droid):
    os.makedirs(OUT, exist_ok=True)
    for name, d in STATIC.items():
        open(os.path.join(OUT, name), "wb").write(get(d + name))
    var = get(BIG)
    for w in (800, 600, 400):
        f = instancer.instantiateVariableFont(TTFont(io.BytesIO(var)), {"wght": w})
        f.save(os.path.join(OUT, f"BigShouldersDisplay-{w}.ttf"))
    open(os.path.join(OUT, "LICENSE-OFL.txt"), "wb").write(get("bigshouldersdisplay/OFL.txt"))
    open(os.path.join(OUT, "LICENSE-OFL-IBMPlex.txt"), "wb").write(get("ibmplexsanscondensed/OFL.txt"))
    opts = subset.Options()
    opts.layout_features = ["*"]
    f = TTFont(droid)
    s = subset.Subsetter(opts)
    s.populate(unicodes=subset.parse_unicodes(KANA))
    s.subset(f)
    f.save(os.path.join(OUT, "KanaSubset.ttf"))
    print("fonts written to", OUT)


if __name__ == "__main__":
    main(sys.argv[1])
