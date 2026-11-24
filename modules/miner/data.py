"""MINER data: XMRig's restricted API summary, MoneroOcean wallet stats, XMR price."""
from dataclasses import dataclass, field

PICO = 1e12          # MoneroOcean amounts are in piconero


@dataclass
class Rig:
    h10: float | None
    h60: float | None
    h15m: float | None
    highest: float | None
    accepted: int
    rejected: int
    pool: str
    ping_ms: int | None
    uptime_s: int
    hugepages: tuple
    threads: int | None
    cpu: str
    paused: bool
    load: list = field(default_factory=list)
    version: str = ""
    diff: int | None = None


@dataclass
class Wallet:
    hash: float
    due_xmr: float
    paid_xmr: float
    valid: int
    invalid: int
    last_share: int | None
    chart: list = field(default_factory=list)      # [(ts_s, hashrate)] oldest first


def parse_summary(p):
    hr = p.get("hashrate", {}).get("total") or [None, None, None]
    c = p.get("connection", {})
    cpu = p.get("cpu", {})
    hp = tuple(p.get("hugepages") or (0, 0))
    return Rig(hr[0], hr[1], hr[2], p.get("hashrate", {}).get("highest"), int(c.get("accepted") or 0),
               int(c.get("rejected") or 0), c.get("pool") or "", c.get("ping"), int(p.get("uptime") or 0), hp,
               cpu.get("threads"), (cpu.get("brand") or "").replace("(R)", "").replace("(TM)", "").replace(" CPU", ""),
               bool(p.get("paused")), list(p.get("resources", {}).get("load_average") or []), p.get("version", ""),
               c.get("diff"))


def parse_wallet(stats, chart=None):
    pts = sorted(((int(c["ts"]) // 1000, float(c["hs"])) for c in (chart or []) if "ts" in c and "hs" in c))
    return Wallet(float(stats.get("hash") or 0), (stats.get("amtDue") or 0) / PICO, (stats.get("amtPaid") or 0) / PICO,
                  int(stats.get("validShares") or 0), int(stats.get("invalidShares") or 0), stats.get("lastHash"), pts)


def parse_price(p):
    return float(p["monero"]["usd"])


def gauge_max(h):
    """A round full-scale value comfortably above the reading."""
    for top in (500, 1000, 2000, 3000, 5000, 10000, 20000, 50000):
        if (h or 0) <= top * 0.85:
            return top
    return 100000


def lamps(rig, wallet):
    """Annunciator panel: (label, state) with state 'ok', 'warn', 'alarm' or 'off'."""
    if rig is None:
        return [("Rig online", "alarm")]
    hp_ok = rig.hugepages and rig.hugepages[1] and rig.hugepages[0] == rig.hugepages[1]
    return [("Rig online", "ok"),
            ("Pool connected", "ok" if rig.pool else "alarm"),
            ("Hashing", "alarm" if rig.paused or not rig.h10 else "ok"),
            ("Huge pages", "ok" if hp_ok else "warn"),
            ("Shares rejected", "warn" if rig.rejected else "off"),
            ("Pool sees rig", "off" if wallet is None else ("ok" if wallet.hash > 0 else "warn"))]
