"""MOST WANTED data: CISA's Known Exploited Vulnerabilities catalog."""
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class Vuln:
    cve: str
    vendor: str
    product: str
    name: str
    desc: str
    added: date
    due: date | None
    ransomware: bool


@dataclass
class Catalog:
    total: int
    released: str
    recent: list            # newest first
    added_30d: int


def _d(s):
    try:
        return date.fromisoformat(s[:10])
    except (TypeError, ValueError):
        return None


def parse(p, today=None):
    today = today or date.today()
    vs = []
    for v in p.get("vulnerabilities", []):
        added = _d(v.get("dateAdded"))
        if not added or not v.get("cveID"):
            continue
        vs.append(Vuln(v["cveID"], v.get("vendorProject", "").strip(), v.get("product", "").strip(),
                       v.get("vulnerabilityName", "").strip(), " ".join(v.get("shortDescription", "").split()),
                       added, _d(v.get("dueDate")), v.get("knownRansomwareCampaignUse") == "Known"))
    if not vs:
        raise ValueError("empty KEV catalog")
    vs.sort(key=lambda v: (v.added, v.cve), reverse=True)
    cutoff = today - timedelta(days=30)
    return Catalog(int(p.get("count") or len(vs)), (p.get("dateReleased") or "")[:10], vs,
                   sum(1 for v in vs if v.added >= cutoff))


def crime(v):
    """The 'wanted for' line: the vulnerability name without the vendor and product it repeats."""
    s = v.name
    for w in (v.vendor, v.product):
        if w and s.lower().startswith(w.lower()):
            s = s[len(w):].strip()
    s = s.removesuffix("Vulnerability").strip()
    return s or "an unnamed vulnerability"
