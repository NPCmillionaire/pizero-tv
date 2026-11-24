"""tvkit — shared look, data plumbing and display host for pizero-tv."""

# mpv processes started by video channels carry this in their command line; the host kills
# leftovers at startup (e.g. after the host itself was OOM-killed).
ORPHAN_MPV = r"input-conf=\S*pizero-tv\S*mpv-input\.conf"
