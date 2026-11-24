"""REGISTRY data: the FAA aircraft registry (from the govint-data release), cut down to a small lookup file."""
import gzip, os, shutil, sqlite3, time
from dataclasses import dataclass

RELEASE = "https://github.com/NPCmillionaire/govint-data/releases/download/faa/faa.sqlite.gz"
MAX_AGE_S = 7 * 86400
REGISTRANT = {"1": "Individual", "2": "Partnership", "3": "Corporation", "4": "Co-owned", "5": "Government",
              "7": "LLC", "8": "Non-citizen corporation", "9": "Non-citizen co-owned"}
KIND = {"1": "Glider", "2": "Balloon", "3": "Blimp", "4": "Single-engine airplane", "5": "Multi-engine airplane",
        "6": "Helicopter", "7": "Weight-shift", "8": "Powered parachute", "9": "Gyroplane", "H": "Hybrid lift",
        "O": "Other"}
KEEP_UPPER = {"LLC", "LP", "LLP", "USA", "US", "II", "III", "IV", "NASA", "FAA", "FBI", "CBP", "DBA", "NA", "PC"}


@dataclass
class Record:
    hex: str
    n: str
    owner: str
    owner_kind: str
    city: str
    state: str
    year: str
    since: str
    make: str
    model: str
    kind: str
    seats: int | None


def nice(s):
    """FAA names are all caps; make them readable without mangling LLC, NASA, McDONNELL and friends."""
    out = []
    for w in (s or "").split():
        core = w.strip(",.&()")
        if core in KEEP_UPPER or any(ch.isdigit() for ch in core):
            out.append(w)
        elif core == "INC":
            out.append(w.replace("INC", "Inc"))
        else:
            out.append(w.capitalize() if "-" not in w else "-".join(p.capitalize() for p in w.split("-")))
    return " ".join(out)


def build(src_sqlite, dest):
    """Write dest: one row per Mode S hex, only the columns the channel shows. No street addresses."""
    tmp = dest + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    con = sqlite3.connect(tmp)
    con.execute("ATTACH DATABASE ? AS faa", (src_sqlite,))
    con.execute("""CREATE TABLE aircraft (hex TEXT PRIMARY KEY, n TEXT, kind_reg TEXT, name TEXT, city TEXT,
                   state TEXT, year TEXT, cert TEXT, mfr TEXT, model TEXT, type TEXT, seats TEXT) WITHOUT ROWID""")
    con.execute("""INSERT OR IGNORE INTO aircraft
                   SELECT upper(trim(m.mode_s_hex)), trim(m.n_number), m.type_registrant, trim(m.name), trim(m.city),
                          trim(m.state), trim(m.year_mfr), trim(m.cert_issue), trim(r.mfr), trim(r.model),
                          trim(r.type_acft), trim(r.seats)
                   FROM faa.faa_master m LEFT JOIN faa.faa_ref r ON r.code = m.mfr_mdl_code
                   WHERE m.mode_s_hex IS NOT NULL AND trim(m.mode_s_hex) != ''""")
    date = con.execute("SELECT value FROM faa.faa_meta WHERE key = 'data_date'").fetchone()
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO meta VALUES ('data_date', ?)", (date[0] if date else "",))
    con.commit()
    con.execute("DETACH DATABASE faa")
    con.close()
    os.replace(tmp, dest)


def ensure(dest, download, now=None):
    """Keep dest at most a week old: download the gzipped release, build, delete the big file. Returns meta."""
    now = now or time.time()
    if not (os.path.exists(dest) and now - os.path.getmtime(dest) < MAX_AGE_S):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        gz, raw = dest + ".src.gz", dest + ".src"
        try:
            download(gz)
            with gzip.open(gz, "rb") as fi, open(raw, "wb") as fo:
                shutil.copyfileobj(fi, fo, 1 << 20)
            os.remove(gz)
            build(raw, dest)
        finally:
            for p in (gz, raw):
                if os.path.exists(p):
                    os.remove(p)
    con = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)
    try:
        date = con.execute("SELECT value FROM meta WHERE key = 'data_date'").fetchone()
        rows = con.execute("SELECT count(*) FROM aircraft").fetchone()[0]
    finally:
        con.close()
    return {"path": dest, "date": date[0] if date else "", "rows": rows}


def lookup(path, hexes):
    """{HEX: Record} for every hex found."""
    hexes = [h.upper() for h in hexes if h]
    if not hexes or not path or not os.path.exists(path):
        return {}
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        q = f"SELECT * FROM aircraft WHERE hex IN ({','.join('?' * len(hexes))})"
        out = {}
        for hx, n, kr, name, city, state, year, cert, mfr, model, typ, seats in con.execute(q, hexes):
            out[hx] = Record(hx, "N" + n if n and not n.startswith("N") else n, nice(name),
                             REGISTRANT.get(kr or "", "Unknown"), nice(city), state or "", year or "",
                             f"{cert[4:6]}/{cert[:4]}" if cert and len(cert) == 8 else "", nice(mfr), model or "",
                             KIND.get(typ or "", "Aircraft"), int(seats) if seats and seats.isdigit() else None)
        return out
    finally:
        con.close()
