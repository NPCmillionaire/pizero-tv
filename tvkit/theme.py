"""Design tokens. See docs/superpowers/specs/2026-11-23-suite-design.md (Visual language)."""


def _hex(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


W, H = 1280, 720
SPINE_W = 150
CONTENT_X0, CONTENT_X1 = 190, 1250

GROUND = _hex("#0C1F24")    # background: deep petrol
TIDE = _hex("#133038")      # hairlines, grids, tracks
BONE = _hex("#EEE6D3")      # primary text, hero numerals
LICHEN = _hex("#86A3A0")    # secondary text, axes
SODIUM = _hex("#FFA630")    # default key, primary data line
CORAL = _hex("#FF5A5F")     # down / alert
SEAGLASS = _hex("#6FD6C5")  # up / live / healthy
DEEP = _hex("#08171B")      # recessed fills (map water, tracks under tracks)

KEYS = {
    "weather": SODIUM, "finance": SEAGLASS, "crypto": _hex("#F7C948"), "threatmap": CORAL,
    "space": _hex("#A88BFF"), "flights": SODIUM, "news": _hex("#7FB2FF"), "syshud": SEAGLASS,
    "lanradar": _hex("#8FE36B"), "sfdispatch": CORAL,
}


def mix(a, b, t):
    """Linear blend of two RGB colors (t=0 → a, t=1 → b)."""
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))
