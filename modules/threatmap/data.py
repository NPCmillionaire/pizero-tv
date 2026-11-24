"""SANS ISC DShield + ip-api + abuse.ch Feodo payloads → attackers, ports, threat level, C2 servers."""
from collections import defaultdict
from dataclasses import dataclass

LEVELS = ("green", "yellow", "orange", "red")
SERVICES = {21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP", 81: "HTTP alt", 110: "POP3",
            123: "NTP", 135: "Windows RPC", 139: "NetBIOS", 143: "IMAP", 161: "SNMP", 443: "HTTPS",
            445: "Windows file sharing", 1433: "SQL Server", 1723: "PPTP VPN", 2323: "Telnet alt", 3306: "MySQL",
            3389: "Remote Desktop", 5060: "SIP phones", 5432: "PostgreSQL", 5555: "Android debug",
            5900: "VNC", 6379: "Redis", 7547: "Router management", 8000: "HTTP alt", 8080: "HTTP proxy",
            8443: "HTTPS alt", 8728: "MikroTik", 9200: "Elasticsearch", 27017: "MongoDB"}


@dataclass
class Attacker:
    ip: str
    targets: int
    reports: int
    first: str
    last: str
    cc: str | None
    country: str | None
    lat: float | None
    lon: float | None
    isp: str | None


@dataclass
class Port:
    rank: int
    port: int
    records: int
    targets: int
    sources: int
    service: str | None


@dataclass
class C2:
    ip: str
    port: int
    malware: str
    online: bool
    cc: str | None
    first_seen: str


def service(port):
    return SERVICES.get(port)


def parse_attackers(p):
    geo = {g.get("query"): g for g in p.get("geo") or [] if isinstance(g, dict)}
    out = []
    for a in p["attacks"]:
        g = geo.get(a["ip"], {})
        ok = g.get("status") == "success"
        out.append(Attacker(a["ip"], int(a.get("attacks") or 0), int(a.get("count") or 0), a.get("firstseen", ""),
                            a.get("lastseen", ""), g.get("countryCode") if ok else None,
                            g.get("country") if ok else None, g.get("lat") if ok else None,
                            g.get("lon") if ok else None, g.get("isp") if ok else None))
    if not out:
        raise ValueError("no attackers")
    return out


def parse_ports(p):
    rows = p.values() if isinstance(p, dict) else p
    out = [Port(int(r["rank"]), int(r["targetport"]), int(r["records"]), int(r["targets"]), int(r["sources"]),
                service(int(r["targetport"]))) for r in rows if isinstance(r, dict) and "targetport" in r]
    if not out:
        raise ValueError("no ports")
    return sorted(out, key=lambda r: r.rank)


def parse_infocon(p):
    s = str(p.get("status", "")).lower()
    if s not in LEVELS:
        raise ValueError(f"unknown infocon level {s!r}")
    return s


def parse_feodo(p):
    return [C2(x["ip_address"], int(x["port"]), x.get("malware") or "unknown", x.get("status") == "online",
               x.get("country"), x.get("first_seen") or "") for x in p]


def by_country(attackers):
    """[(cc, country, number of attacking IPs, total reports)], most IPs first."""
    agg = defaultdict(lambda: [None, 0, 0])
    for a in attackers:
        if a.cc:
            row = agg[a.cc]
            row[0], row[1], row[2] = a.country, row[1] + 1, row[2] + a.reports
    return sorted(((cc, n, ips, rep) for cc, (n, ips, rep) in agg.items()), key=lambda r: (-r[2], -r[3]))
