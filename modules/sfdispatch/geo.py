"""Lon/lat -> screen projection for the San Francisco map."""
import math

# lon_min, lat_min, lon_max, lat_max
BBOX = (-122.515, 37.705, -122.355, 37.815)
_KX = math.cos(math.radians(37.76))


class Projector:
    """Equirectangular projection fitted (aspect-preserving, centered) into rect."""

    def __init__(self, rect):
        x, y, w, h = rect
        gw = (BBOX[2] - BBOX[0]) * _KX
        gh = BBOX[3] - BBOX[1]
        self.scale = min(w / gw, h / gh)
        self.ox = x + (w - gw * self.scale) / 2
        self.oy = y + (h - gh * self.scale) / 2

    def to_px(self, lon, lat):
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            return None
        return (round(self.ox + (lon - BBOX[0]) * _KX * self.scale),
                round(self.oy + (BBOX[3] - lat) * self.scale))
