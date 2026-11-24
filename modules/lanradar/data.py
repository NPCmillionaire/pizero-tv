"""Devices on the local network: neighbor table, ping sweep results, vendor names. Stays on the Pi."""
import gzip, ipaddress, json, os, time
from dataclasses import dataclass
from functools import lru_cache

OUI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oui.tsv.gz")
BAD_STATES = {"FAILED", "INCOMPLETE", "NOARP"}
NEW_FOR_S = 86400


@dataclass
class Device:
    ip: str
    mac: str
    state: str
    name: str | None
    rtt_ms: float | None
    vendor: str | None
    new: bool

    @property
    def label(self):
        if self.name:
            return self.name
        if self.vendor and self.vendor != "Private address":
            return f"{self.vendor} device"
        return "Unnamed device"


@lru_cache(maxsize=1)
def _oui():
    with gzip.open(OUI, "rt") as fh:
        return dict(line.rstrip("\n").split("\t", 1) for line in fh)


def vendor(mac):
    first = int(mac[:2], 16)
    if first & 0x02:                     # locally administered: phones' randomized "private" addresses
        return "Private address"
    return _oui().get(mac.replace(":", "").upper()[:6])


def parse_ip_neigh(raw):
    out = []
    for r in json.loads(raw):
        ip, mac = r.get("dst", ""), r.get("lladdr")
        state = (r.get("state") or ["UNKNOWN"])[0]
        if ":" in ip or not mac or state in BAD_STATES:
            continue
        out.append({"ip": ip, "mac": mac.lower(), "state": state})
    return out


def parse_devices(rows, known, now=None):
    """rows: [{ip, mac, state, name, rtt_ms}]. known: {mac: first_seen}, updated in place.

    A device is new when it first appeared after the very first scan, within the last day.
    """
    now = now or time.time()
    primed = known.get("__primed__") or (min(v for k, v in known.items() if k != "__primed__") if known else now)
    known["__primed__"] = primed
    out = []
    for r in rows:
        if r.get("state") in BAD_STATES or not r.get("mac") or r["mac"] == "00:00:00:00:00:00":
            continue
        mac = r["mac"].lower()
        first = known.setdefault(mac, now)
        out.append(Device(r["ip"], mac, r.get("state", ""), r.get("name"), r.get("rtt_ms"), vendor(mac),
                          first > primed and now - first < NEW_FOR_S))
    return sorted(out, key=lambda d: ipaddress.ip_address(d.ip))


def hosts(subnet):
    net = ipaddress.ip_network(subnet, strict=False)
    if net.num_addresses > 1024:
        raise ValueError(f"{subnet} is too big to sweep from a Pi Zero; use a /22 or smaller")
    return [str(h) for h in net.hosts()]
