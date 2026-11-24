"""WEATHER — conditions, the next 24 hours, the sun, and the week, for the configured place."""
import time
from datetime import datetime

import pygame
import requests

from tvkit import fx, text, theme
from tvkit.module import Module

from . import data, icons

URL = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
       "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,"
       "wind_direction_10m,wind_gusts_10m,is_day"
       "&hourly=temperature_2m,precipitation_probability,weather_code&forecast_hours=25"
       "&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max"
       "&forecast_days=7&timezone=auto&temperature_unit={tu}&wind_speed_unit={wu}")
PAGE_S = 10                      # each forecast page holds for ten seconds, then the next
PAGES = ("Current conditions", "The next 24 hours", "The week ahead")
# local-forecast station palette: deep cable blue, a brighter panel, warm yellow headings
SKY_TOP, SKY_BOTTOM = (14, 26, 104), (52, 22, 98)
PANEL, PANEL_HI, PANEL_LO = (26, 52, 150), (98, 138, 230), (10, 20, 72)
WHITE, PALE, GOLD = (255, 255, 255), (170, 196, 255), (255, 214, 80)
WET = (120, 200, 255)
BOX = pygame.Rect(40, 112, 1200, 506)
CRAWL = pygame.Rect(0, 636, 1280, 44)


def _ampm(t):
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'am' if t.hour < 12 else 'pm'}"


class Weather(Module):
    name, title, key = "weather", "WEATHER", theme.KEYS["weather"]
    blurb = "The local forecast: conditions, the next 24 hours and the week"
    order = 10
    fps = 20
    footer_color = PALE

    def start(self, ctx):
        super().start(ctx)
        self.place = ctx.config.place
        self.metric = ctx.config.units_temp == "C"
        self._minute, self.page, self._crawl, self._crawl_key = None, 0, None, None
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
        page = int(now // PAGE_S) % len(PAGES)
        if page != self.page:
            self.page, changed = page, True
        return changed

    # -- the station -------------------------------------------------------------
    def draw_frame(self, surf):
        surf.blit(fx.gradient((theme.W, theme.H), SKY_TOP, SKY_BOTTOM), (0, 0))
        title = self.place.name if self.place else "Your local forecast"
        text.draw(surf, "Your local forecast", (44, 22), "geo", 22, PALE)
        text.draw(surf, title, (42, 44), "geo-700", 46, WHITE, max_w=760)
        now = datetime.now()
        text.draw(surf, _ampm(now), (1238, 18), "geo-700", 50, WHITE, anchor="topright")
        text.draw(surf, now.strftime("%A %-d %B"), (1238, 76), "geo", 20, PALE, anchor="topright")
        _bevel(surf, BOX)
        pygame.draw.rect(surf, PANEL_LO, CRAWL)
        pygame.draw.line(surf, GOLD, CRAWL.topleft, CRAWL.topright, 2)

    def draw_static(self, surf):
        x, y = BOX.left + 30, BOX.top + 22
        if not self.place:
            text.draw(surf, "No place set", (x, y + 90), "geo-700", 90, WHITE)
            text.draw(surf, "Add a [place] with name, lat and lon to ~/.config/pizero-tv/config.toml.",
                      (x, y + 220), "geo", 26, PALE, max_w=BOX.width - 60)
            return
        w = self.src.value
        if w is None:
            msg = {"offline": "Open-Meteo isn't answering. The forecast will appear when it does.",
                   "waiting": "Fetching the forecast from Open-Meteo."}.get(self.src.status, "")
            text.draw(surf, "Stand by", (x, y + 90), "geo-700", 110, WHITE)
            text.draw(surf, msg, (x, y + 250), "geo", 28, PALE, max_w=BOX.width - 60)
            return
        text.draw(surf, PAGES[self.page], (x, y), "geo-700", 34, GOLD)
        for i in range(len(PAGES)):                       # which page of the loop this is
            c = GOLD if i == self.page else PANEL_HI
            pygame.draw.circle(surf, c, (BOX.right - 40 - (len(PAGES) - 1 - i) * 24, y + 20), 7)
        (self._now_page, self._hours_page, self._week_page)[self.page](surf, w)

    def draw_live(self, surf, t):
        w = self.src.value if self.place else None
        if w is None:
            return False
        key = (id(w), self._minute)
        if key != self._crawl_key:
            self._crawl, self._crawl_key = fx.Crawl(self._crawl_items(w), "geo", 26, WHITE, speed=80,
                                                    sep="     ", sep_color=GOLD), key
        pygame.draw.rect(surf, PANEL_LO, CRAWL.inflate(0, -4).move(0, 2))
        self._crawl.draw(surf, CRAWL.inflate(-40, -4).move(0, 2), t)
        return True

    # -- pages ---------------------------------------------------------------------
    def _now_page(self, surf, w):
        x0, top = BOX.left + 40, BOX.top + 80
        r = text.draw(surf, f"{round(w.temp)}°", (x0 - 8, top - 10), "geo-700", 230, WHITE)
        cond, icon = data.condition(w.code)
        icons.draw(surf, icon, (r.right + 120, top + 140), 190, night=not w.is_day, bg=PANEL)
        text.draw(surf, cond, (x0, top + 300), "geo-700", 48, GOLD, max_w=620)
        o = data.outlook(w)
        if o:
            text.draw(surf, o[0].upper() + o[1:] + ".", (x0, top + 362), "geo", 26, WET, max_w=640)
        unit = "km/h" if self.metric else "mph"
        today = w.days[0]
        rows = [("Feels like", f"{round(w.feels)}°"), ("Humidity", f"{w.humidity}%"),
                ("Wind", f"{data.compass(w.wind_dir)} {round(w.wind)} {unit}"),
                ("Gusts", f"{round(w.gust)} {unit}"), ("Sunrise", _ampm(today.sunrise)),
                ("Sunset", _ampm(today.sunset))]
        lx, rx = 760, BOX.right - 40
        for i, (k, v) in enumerate(rows):
            y = top + 4 + i * 62
            text.draw(surf, k, (lx, y), "geo", 30, PALE)
            text.draw(surf, v, (rx, y - 4), "geo-700", 36, WHITE, anchor="topright")
            if i < len(rows) - 1:
                pygame.draw.line(surf, PANEL_HI, (lx, y + 50), (rx, y + 50), 1)

    def _hours_page(self, surf, w):
        x, y, cw, ch = BOX.left + 70, BOX.top + 110, BOX.width - 140, 300
        hours = w.hours[:25]
        temps = [h.temp for h in hours]
        lo, hi = min(temps), max(temps)
        span = max(hi - lo, 4)
        step = cw / (len(hours) - 1)
        pts = [(x + i * step, y + ch - 50 - (t - lo) / span * (ch - 110)) for i, t in enumerate(temps)]
        for i, h in enumerate(hours):
            if h.pop:
                bh = h.pop / 100 * 90
                pygame.draw.rect(surf, theme.mix(PANEL, WET, 0.6), (x + i * step - 7, y + ch - bh, 14, bh))
        pygame.draw.line(surf, PANEL_HI, (x, y + ch), (x + cw, y + ch), 2)
        pygame.draw.lines(surf, GOLD, False, pts, 5)
        for i in range(0, len(hours), 3):
            px, py = pts[i]
            pygame.draw.circle(surf, WHITE, (int(px), int(py)), 5)
            text.draw(surf, f"{round(temps[i])}°", (px, py - 12), "geo-700", 30, WHITE, anchor="midbottom")
            text.draw(surf, "Now" if i == 0 else data._hour_text(hours[i].time), (px, y + ch + 12), "geo", 22,
                      PALE, anchor="midtop")
        text.draw(surf, "Blue bars are the chance of rain", (BOX.right - 40, BOX.bottom - 22), "geo", 20, PALE,
                  anchor="bottomright")

    def _week_page(self, surf, w):
        days = w.days[:7]
        colw = (BOX.width - 40) // max(1, len(days))
        top = BOX.top + 90
        for i, d in enumerate(days):
            x = BOX.left + 20 + i * colw
            cx = x + colw // 2
            if i:
                pygame.draw.line(surf, PANEL_HI, (x, top), (x, BOX.bottom - 30), 1)
            text.draw(surf, "Today" if i == 0 else d.date.strftime("%a"), (cx, top), "geo-700", 32, GOLD,
                      anchor="midtop")
            icons.draw(surf, data.condition(d.code)[1], (cx, top + 110), 86, bg=PANEL)
            text.draw(surf, f"{round(d.hi)}°", (cx, top + 180), "geo-700", 62, WHITE, anchor="midtop")
            text.draw(surf, f"{round(d.lo)}°", (cx, top + 256), "geo", 42, PALE, anchor="midtop")
            cond = data.condition(d.code)[0]
            for j, line in enumerate(text.wrap(cond, "geo", 20, colw - 16)[:2]):
                text.draw(surf, line, (cx, top + 320 + j * 24), "geo", 20, WHITE, anchor="midtop", max_w=colw - 16)
            if d.pop >= 30:
                text.draw(surf, f"{d.pop}% rain", (cx, top + 380), "geo-700", 22, WET, anchor="midtop",
                          max_w=colw - 10)

    def _crawl_items(self, w):
        unit = "km/h" if self.metric else "mph"
        today = w.days[0]
        hrs, mins = divmod(int((today.sunset - today.sunrise).total_seconds() // 60), 60)
        items = [f"Now {round(w.temp)}° and {data.condition(w.code)[0].lower()}",
                 f"Today's high {round(today.hi)}°, low {round(today.lo)}°",
                 f"Wind {data.compass(w.wind_dir)} at {round(w.wind)} {unit}",
                 f"Sunrise {_ampm(today.sunrise)}, sunset {_ampm(today.sunset)}, {hrs}h {mins}m of daylight"]
        o = data.outlook(w)
        if o:
            items.insert(1, o[0].upper() + o[1:])
        if len(w.days) > 1:
            t = w.days[1]
            items.append(f"Tomorrow {data.condition(t.code)[0].lower()}, {round(t.hi)}° / {round(t.lo)}°")
        return items


def _bevel(surf, r):
    """A raised local-forecast panel: lighter top-left edge, darker bottom-right."""
    pygame.draw.rect(surf, PANEL, r)
    pygame.draw.line(surf, PANEL_HI, r.topleft, (r.right - 1, r.top), 3)
    pygame.draw.line(surf, PANEL_HI, r.topleft, (r.left, r.bottom - 1), 3)
    pygame.draw.line(surf, PANEL_LO, (r.left, r.bottom - 1), (r.right - 1, r.bottom - 1), 3)
    pygame.draw.line(surf, PANEL_LO, (r.right - 1, r.top), (r.right - 1, r.bottom - 1), 3)


def _until(a, b):
    m = int((b - a).total_seconds() // 60)
    return f"{m // 60}h {m % 60}m" if m >= 60 else f"{m}m"


MODULE = Weather
