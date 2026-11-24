"""Open-Meteo forecast → plain values for the WEATHER screen."""
from dataclasses import dataclass
from datetime import date, datetime

ICONS = ("sun", "moon", "partly", "cloud", "fog", "drizzle", "rain", "snow", "showers", "thunder")
WMO = {
    0: ("Clear", "sun"), 1: ("Mostly clear", "sun"), 2: ("Partly cloudy", "partly"), 3: ("Overcast", "cloud"),
    45: ("Fog", "fog"), 48: ("Freezing fog", "fog"),
    51: ("Light drizzle", "drizzle"), 53: ("Drizzle", "drizzle"), 55: ("Heavy drizzle", "drizzle"),
    56: ("Freezing drizzle", "drizzle"), 57: ("Heavy freezing drizzle", "drizzle"),
    61: ("Light rain", "rain"), 63: ("Rain", "rain"), 65: ("Heavy rain", "rain"),
    66: ("Freezing rain", "rain"), 67: ("Heavy freezing rain", "rain"),
    71: ("Light snow", "snow"), 73: ("Snow", "snow"), 75: ("Heavy snow", "snow"), 77: ("Snow grains", "snow"),
    80: ("Rain showers", "showers"), 81: ("Heavy showers", "showers"), 82: ("Violent showers", "showers"),
    85: ("Snow showers", "snow"), 86: ("Heavy snow showers", "snow"),
    95: ("Thunderstorms", "thunder"), 96: ("Thunderstorms with hail", "thunder"),
    99: ("Severe thunderstorms with hail", "thunder"),
}
POINTS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


@dataclass
class Hour:
    time: datetime
    temp: float
    pop: int
    code: int


@dataclass
class Day:
    date: date
    code: int
    hi: float
    lo: float
    sunrise: datetime
    sunset: datetime
    pop: int


@dataclass
class Weather:
    now: datetime
    temp: float
    feels: float
    humidity: int
    code: int
    wind: float
    wind_dir: int
    gust: float
    is_day: bool
    hours: list
    days: list


def _dt(s):
    return datetime.fromisoformat(s)


def parse(p):
    c, h, d = p["current"], p["hourly"], p["daily"]
    hours = [Hour(_dt(t), float(tp), int(pp or 0), int(wc))
             for t, tp, pp, wc in zip(h["time"], h["temperature_2m"], h["precipitation_probability"], h["weather_code"])]
    days = [Day(date.fromisoformat(t), int(wc), float(hi), float(lo), _dt(sr), _dt(ss), int(pp or 0))
            for t, wc, hi, lo, sr, ss, pp in zip(d["time"], d["weather_code"], d["temperature_2m_max"],
                                                 d["temperature_2m_min"], d["sunrise"], d["sunset"],
                                                 d["precipitation_probability_max"])]
    if not hours or not days:
        raise ValueError("forecast has no hours or days")
    return Weather(_dt(c["time"]), float(c["temperature_2m"]), float(c["apparent_temperature"]),
                   int(c["relative_humidity_2m"]), int(c["weather_code"]), float(c["wind_speed_10m"]),
                   int(c["wind_direction_10m"]), float(c["wind_gusts_10m"]), bool(c["is_day"]), hours, days)


def condition(code):
    return WMO.get(code, ("Unknown conditions", "cloud"))


def sun_fraction(now, sunrise, sunset):
    """0 at sunrise, 1 at sunset, None while the sun is down."""
    if not (sunrise <= now <= sunset):
        return None
    return (now - sunrise).total_seconds() / (sunset - sunrise).total_seconds()


def compass(deg):
    return POINTS[round((deg % 360) / 22.5) % 16]


def _hour_text(t):
    h = t.hour % 12 or 12
    return f"{h} {'am' if t.hour < 12 else 'pm'}"


def outlook(w):
    """One sentence about precipitation in the next 12 hours, or None when it's dry."""
    wet = [h for h in w.hours[1:13] if h.pop >= 40]
    if not wet:
        return None
    first = wet[0]
    kind = "snow" if condition(first.code)[1] == "snow" else "rain"
    peak = max(h.pop for h in wet)
    return f"{peak}% chance of {kind} from {_hour_text(first.time)}"
