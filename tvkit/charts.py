"""Small chart primitives shared by the data screens."""
import pygame

from . import theme


def _scale(values, lo, hi, y, h):
    span = (hi - lo) or 1.0
    return [y + h - (v - lo) / span * h for v in values]


def sparkline(surf, rect, values, color, width=2, baseline=None):
    """Line through `values` across rect. baseline: draw a dotted reference level (e.g. previous close)."""
    x, y, w, h = rect
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return
    lo, hi = min(vals + ([baseline] if baseline is not None else [])), max(vals + ([baseline] if baseline is not None else []))
    pad = width
    ys = _scale(vals, lo, hi, y + pad, h - 2 * pad)
    pts = [(x + i * (w - 1) / (len(vals) - 1), yy) for i, yy in enumerate(ys)]
    if baseline is not None:
        by = _scale([baseline], lo, hi, y + pad, h - 2 * pad)[0]
        for bx in range(int(x), int(x + w), 8):
            pygame.draw.line(surf, theme.TIDE, (bx, by), (min(bx + 3, x + w - 1), by), 1)
    pygame.draw.lines(surf, color, False, pts, width)


def candles(surf, rect, o, h, l, c, up=theme.SEAGLASS, down=theme.CORAL, ma=None, ma_color=theme.SODIUM):
    """OHLC candles across rect; returns the (low, high) price range drawn."""
    x, y, w, hh = rect
    n = len(c)
    if n == 0:
        return None
    lo, hi = min(l), max(h)
    step = w / n
    body = max(2, int(step * 0.62))
    sy = lambda v: y + hh - (v - lo) / ((hi - lo) or 1.0) * hh
    for i in range(n):
        cx = int(x + step * i + step / 2)
        col = up if c[i] >= o[i] else down
        pygame.draw.line(surf, col, (cx, sy(h[i])), (cx, sy(l[i])), 1)
        top, bot = sy(max(o[i], c[i])), sy(min(o[i], c[i]))
        pygame.draw.rect(surf, col, (cx - body // 2, top, body, max(1, bot - top)))
    if ma:
        pts = [(x + step * i + step / 2, sy(v)) for i, v in enumerate(ma) if v is not None]
        if len(pts) >= 2:
            pygame.draw.lines(surf, ma_color, False, pts, 2)
    return lo, hi
