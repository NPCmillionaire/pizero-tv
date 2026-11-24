"""WEATHER — conditions, the next 24 hours, the sun, and the week, for the configured place."""
import math, time
from datetime import datetime

import pygame
import requests

from tvkit import text, theme
from tvkit.module import Module

from . import data, icons

URL = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
       "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,"
       "wind_direction_10m,wind_gusts_10m,is_day"
       "&hourly=temperature_2m,precipitation_probability,weather_code&forecast_hours=25"
       "&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max"
       "&forecast_days=7&timezone=auto&temperature_unit={tu}&wind_speed_unit={wu}")
X0 = 190
CHART = (790, 96, 450, 230)
SUN = (790, 410, 450, 110)
WET = (127, 178, 255)


def _ampm(t):
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'am' if t.hour < 12 else 'pm'}"


class Weather(Module):
    name, title, key = "weather", "WEATHER", theme.KEYS["weather"]
    blurb = "Conditions, the next 24 hours and the week ahead"
    order = 10

    def start(self, ctx):
        super().start(ctx)
        self.place = ctx.config.place
        self.metric = ctx.config.units_temp == "C"
        self._minute = None
        if self.place:
            url = URL.format(lat=self.place.lat, lon=self.place.lon, tu="celsius" if self.metric else "fahrenheit",
                             wu="kmh" if self.metric else "mph")
            self.src = self.source("forecast", lambda: requests.get(url, timeout=15).json(), 600,
                                   parse=data.parse)

    def update(self, now):
        changed = super().update(now)
        m = time.strftime("%H:%M")
        if m != self._minute:
            self._minute, changed = m, True
        return changed

    # ----------------------------------------------------------------------------
    def draw_static(self, surf):
        if not self.place:
            text.draw(surf, "No place set", (X0, 200), "display", 120, theme.BONE)
            text.draw(surf, "Add a [place] with name, lat and lon to ~/.config/pizero-tv/config.toml.",
                      (X0, 360), "sans", 24, theme.LICHEN, max_w=1050)
            return
        w = self.src.value
        text.draw(surf, self.place.name, (X0, 34), "sans-600", 24, theme.BONE, max_w=560)
        when = w.now.strftime("%A %-d %B") + f", observed {_ampm(w.now)}" if w else datetime.now().strftime("%A %-d %B")
        text.draw(surf, when, (X0, 64), "sans", 20, theme.LICHEN, max_w=560)
        if w is None:
            msg = {"offline": "Open-Meteo isn't answering. The forecast will appear when it does.",
                   "waiting": "Fetching the forecast from Open-Meteo."}.get(self.src.status, "")
            text.draw(surf, "—", (X0 - 6, 90), "display", 300, theme.TIDE)
            text.draw(surf, msg, (X0, 440), "sans", 24, theme.LICHEN, max_w=1050)
            return
        self._hero(surf, w)
        self._chart(surf, w)
        self._sun(surf, w)
        self._week(surf, w)

    def _hero(self, surf, w):
        r = text.draw(surf, f"{round(w.temp)}°", (X0 - 10, 84), "display", 300, theme.BONE)
        cond, icon = data.condition(w.code)
        icons.draw(surf, icon, (min(r.right + 90, 700), 250), 150, night=not w.is_day)
        text.draw(surf, cond, (X0, 404), "display-400", 58, self.key, max_w=590)
        unit = "km/h" if self.metric else "mph"
        gust = f", gusts {round(w.gust)}" if w.gust - w.wind >= 5 else ""
        text.draw(surf, f"Feels like {round(w.feels)}°. Wind {data.compass(w.wind_dir)} {round(w.wind)} {unit}{gust}. "
                        f"Humidity {w.humidity}%.", (X0, 476), "sans", 22, theme.LICHEN, max_w=590)
        o = data.outlook(w)
        if o:
            text.draw(surf, o[0].upper() + o[1:] + ".", (X0, 508), "sans-500", 22, WET, max_w=590)

    def _chart(self, surf, w):
        x, y, cw, ch = CHART
        text.draw(surf, "Next 24 hours", (x, y - 50), "sans-500", 20, theme.BONE)
        hours = w.hours[:25]
        temps = [h.temp for h in hours]
        lo, hi = min(temps), max(temps)
        span = max(hi - lo, 4)
        pts = [(x + i * cw / (len(hours) - 1), y + ch - 30 - (t - lo) / span * (ch - 60)) for i, t in enumerate(temps)]
        for i, h in enumerate(hours):            # precipitation chance as bars under the curve
            if h.pop:
                bh = h.pop / 100 * 60
                bx = x + i * cw / (len(hours) - 1) - 5
                pygame.draw.rect(surf, theme.mix(theme.GROUND, WET, 0.55), (bx, y + ch - bh, 10, bh))
        pygame.draw.line(surf, theme.TIDE, (x, y + ch), (x + cw, y + ch), 1)
        pygame.draw.lines(surf, self.key, False, pts, 3)
        imax, imin = temps.index(hi), temps.index(lo)
        for i, col in ((imax, theme.BONE), (imin, theme.LICHEN)):
            px, py = pts[i]
            pygame.draw.circle(surf, col, (int(px), int(py)), 5)
            anchor = "midbottom" if i == imax else "midtop"
            text.draw(surf, f"{round(temps[i])}°", (min(max(px, x + 20), x + cw - 20), py - 10 if i == imax else py + 10),
                      "display-600", 30, col, anchor=anchor)
        for i in range(0, len(hours), 6):
            hx = x + i * cw / (len(hours) - 1)
            text.draw(surf, "now" if i == 0 else data._hour_text(hours[i].time), (hx, y + ch + 10), "sans", 16,
                      theme.LICHEN, anchor="midtop")
        text.draw(surf, "Bars show the chance of rain", (x + cw, y - 46), "sans", 16, theme.LICHEN,
                  anchor="topright")

    def _sun(self, surf, w):
        x, y, sw, sh = SUN
        today = w.days[0]
        cx, base, rad, ry = x + sw // 2, y + sh, sw // 2 - 50, sh - 24
        rect = pygame.Rect(cx - rad, base - ry, 2 * rad, 2 * ry)
        pygame.draw.arc(surf, theme.TIDE, rect, 0, math.pi, 2)
        pygame.draw.line(surf, theme.TIDE, (x, base), (x + sw, base), 1)
        f = data.sun_fraction(w.now, today.sunrise, today.sunset)
        if f is not None:
            pygame.draw.arc(surf, self.key, rect, math.pi * (1 - f), math.pi, 3)
            a = math.pi * (1 - f)
            pygame.draw.circle(surf, self.key, (int(cx + rad * math.cos(a)), int(base - ry * math.sin(a))), 9)
        text.draw(surf, f"Sunrise {_ampm(today.sunrise)}", (x, base + 10), "sans", 18, theme.LICHEN)
        text.draw(surf, f"Sunset {_ampm(today.sunset)}", (x + sw, base + 10), "sans", 18, theme.LICHEN,
                  anchor="topright")
        day = today.sunset - today.sunrise
        hrs, mins = divmod(int(day.total_seconds() // 60), 60)
        if f is not None:
            label = f"{hrs}h {mins}m of daylight"
        elif w.now < today.sunrise:
            label = f"Sunrise in {_until(w.now, today.sunrise)}"
        elif len(w.days) > 1:
            label = f"Sunrise in {_until(w.now, w.days[1].sunrise)}"
        else:
            label = "The sun is down"
        text.draw(surf, label, (cx, base - ry // 2), "sans-500", 18, theme.BONE, anchor="center")

    def _week(self, surf, w):
        y = 576
        pygame.draw.line(surf, theme.TIDE, (X0, y - 22), (1250, y - 22), 1)
        colw = (1250 - X0) // 7
        for i, d in enumerate(w.days[:7]):
            x = X0 + i * colw
            text.draw(surf, "Today" if i == 0 else d.date.strftime("%a"), (x, y), "sans-500", 20, theme.BONE)
            icons.draw(surf, data.condition(d.code)[1], (x + colw - 44, y + 12), 40, muted=True)
            r = text.draw(surf, f"{round(d.hi)}°", (x, y + 28), "display", 56, theme.BONE)
            text.draw(surf, f"{round(d.lo)}°", (r.right + 8, y + 44), "display-400", 38, theme.LICHEN,
                      max_w=colw - r.width - 14)
            if d.pop >= 30:
                text.draw(surf, f"{d.pop}% rain", (x, y + 92), "sans", 16, WET, max_w=colw - 10)


def _until(a, b):
    m = int((b - a).total_seconds() // 60)
    return f"{m // 60}h {m % 60}m" if m >= 60 else f"{m}m"


MODULE = Weather
