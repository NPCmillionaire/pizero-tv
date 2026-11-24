"""adsb.lol /v2/point payload → aircraft around the configured place."""
import math
from dataclasses import dataclass

AIRLINES = {"UAL": "United", "AAL": "American", "DAL": "Delta", "SWA": "Southwest", "ASA": "Alaska",
            "SKW": "SkyWest", "JBU": "JetBlue", "FFT": "Frontier", "NKS": "Spirit", "HAL": "Hawaiian",
            "QXE": "Horizon", "ENY": "Envoy", "RPA": "Republic", "EDV": "Endeavor", "JIA": "PSA",
            "FDX": "FedEx", "UPS": "UPS", "GTI": "Atlas Air", "ABX": "ABX Air", "BAW": "British Airways",
            "AFR": "Air France", "DLH": "Lufthansa", "KLM": "KLM", "ACA": "Air Canada", "WJA": "WestJet",
            "UAE": "Emirates", "QTR": "Qatar Airways", "SIA": "Singapore Airlines", "CPA": "Cathay Pacific",
            "JAL": "Japan Airlines", "ANA": "All Nippon", "KAL": "Korean Air", "EVA": "EVA Air",
            "CAL": "China Airlines", "QFA": "Qantas", "ANZ": "Air New Zealand", "AMX": "Aeromexico",
            "VOI": "Volaris", "VIV": "Viva Aerobus", "AAY": "Allegiant", "SCX": "Sun Country", "MXY": "Breeze",
            "EJA": "NetJets", "LXJ": "Flexjet", "CKS": "Kalitta", "VIR": "Virgin Atlantic", "IBE": "Iberia",
            "THY": "Turkish", "ETD": "Etihad", "CCA": "Air China", "CES": "China Eastern", "CSN": "China Southern"}
TYPES = {"B738": "Boeing 737-800", "B739": "Boeing 737-900", "B737": "Boeing 737-700", "B38M": "Boeing 737 MAX 8",
         "B39M": "Boeing 737 MAX 9", "B752": "Boeing 757-200", "B753": "Boeing 757-300", "B763": "Boeing 767-300",
         "B772": "Boeing 777-200", "B77W": "Boeing 777-300ER", "B77L": "Boeing 777-200LR", "B788": "Boeing 787-8",
         "B789": "Boeing 787-9", "B78X": "Boeing 787-10", "B744": "Boeing 747-400", "B748": "Boeing 747-8",
         "A319": "Airbus A319", "A320": "Airbus A320", "A321": "Airbus A321", "A20N": "Airbus A320neo",
         "A21N": "Airbus A321neo", "A332": "Airbus A330-200", "A333": "Airbus A330-300", "A339": "Airbus A330-900",
         "A359": "Airbus A350-900", "A35K": "Airbus A350-1000", "A388": "Airbus A380", "BCS3": "Airbus A220-300",
         "E75L": "Embraer 175", "E75S": "Embraer 175", "E170": "Embraer 170", "E190": "Embraer 190",
         "CRJ2": "Bombardier CRJ200", "CRJ7": "Bombardier CRJ700", "CRJ9": "Bombardier CRJ900",
         "DH8D": "Dash 8-400", "C172": "Cessna 172", "C182": "Cessna 182", "C208": "Cessna Caravan",
         "PC12": "Pilatus PC-12", "SR22": "Cirrus SR22", "GLF4": "Gulfstream IV", "GLF5": "Gulfstream V",
         "GLF6": "Gulfstream G650", "CL60": "Challenger 600", "E55P": "Phenom 300", "C68A": "Citation Latitude",
         "B06": "Bell 206", "EC35": "Airbus H135", "AS50": "Airbus H125", "R44": "Robinson R44"}
EMERGENCY = {"7500": "hijack", "7600": "radio failure", "7700": "general emergency"}


@dataclass
class Aircraft:
    hex: str
    callsign: str
    reg: str
    type: str
    alt: int
    on_ground: bool
    speed: float | None
    track: float | None
    rate: int | None
    squawk: str | None
    lat: float
    lon: float
    dist_nm: float
    bearing: float
    emergency: str | None


def bearing_distance(lat0, lon0, lat, lon):
    """Great-circle distance (nautical miles) and initial bearing (degrees) from home."""
    p0, p1 = math.radians(lat0), math.radians(lat)
    dl = math.radians(lon - lon0)
    a = math.sin((p1 - p0) / 2) ** 2 + math.cos(p0) * math.cos(p1) * math.sin(dl / 2) ** 2
    d = 2 * 3440.065 * math.asin(math.sqrt(a))
    b = math.degrees(math.atan2(math.sin(dl) * math.cos(p1),
                                math.cos(p0) * math.sin(p1) - math.sin(p0) * math.cos(p1) * math.cos(dl)))
    return d, b % 360


def airline(callsign):
    cs = (callsign or "").strip().upper()
    if len(cs) >= 4 and cs[:3].isalpha() and cs[3].isdigit():
        return AIRLINES.get(cs[:3])
    return None


def type_name(code):
    return TYPES.get(code, code)


def parse(p, lat0, lon0):
    out = []
    for a in p["ac"]:
        if "lat" not in a or "lon" not in a:
            continue
        d, b = bearing_distance(lat0, lon0, a["lat"], a["lon"])
        alt = a.get("alt_baro")
        ground = alt == "ground"
        out.append(Aircraft(a["hex"], (a.get("flight") or "").strip() or a.get("r") or a["hex"].upper(),
                            a.get("r") or "", a.get("t") or "", 0 if ground or alt is None else int(alt), ground,
                            a.get("gs"), a.get("track"), a.get("baro_rate"), a.get("squawk"), a["lat"], a["lon"],
                            d, b, EMERGENCY.get(a.get("squawk") or "")))
    return sorted(out, key=lambda x: x.dist_nm)
