"""Local system telemetry: psutil snapshots, Pi temperature and throttling flags."""
import collections, os, re, subprocess, time

FLAGS = {0: "under-voltage", 1: "frequency capped", 2: "throttled", 3: "soft temperature limit"}


class History:
    def __init__(self, n):
        self._d = collections.deque(maxlen=n)

    def add(self, v):
        self._d.append(v)

    @property
    def values(self):
        return list(self._d)


def parse_vcgencmd_temp(raw):
    m = re.search(r"temp=([\d.]+)", raw)
    if not m:
        raise ValueError(f"no temperature in {raw!r}")
    return float(m.group(1))


def parse_sysfs_temp(raw):
    return int(raw.strip()) / 1000


def parse_throttled(raw):
    m = re.search(r"throttled=0x([0-9a-fA-F]+)", raw)
    if not m:
        raise ValueError(f"no throttle state in {raw!r}")
    v = int(m.group(1), 16)
    return {"now": [n for b, n in FLAGS.items() if v & (1 << b)],
            "since_boot": [n for b, n in FLAGS.items() if v & (1 << (b + 16))]}


def rates(prev, cur):
    if not prev:
        return None, None
    dt = cur["t"] - prev["t"]
    if dt <= 0:
        return None, None
    return (cur["rx"] - prev["rx"]) / dt, (cur["tx"] - prev["tx"]) / dt


def uptime_text(secs):
    if secs < 60:
        return "under a minute"
    d, rem = divmod(int(secs), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d} day{'s' if d != 1 else ''}, {h} hours"
    return f"{h} hours, {m} minutes" if h else f"{m} minutes"


def human_rate(b):
    if b < 1024:
        return f"{b:.0f} B/s"
    if b < 1024 * 1024:
        return f"{b / 1024:.1f} KB/s"
    return f"{b / 1024 / 1024:.1f} MB/s"


# -- collectors (run on the Pi; JSON-able so fixtures and cache work) -------------------
def snapshot():
    import psutil
    vm, sw, net = psutil.virtual_memory(), psutil.swap_memory(), psutil.net_io_counters()
    temp = None
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as fh:
            temp = parse_sysfs_temp(fh.read())
    except OSError:
        pass
    return {"t": time.time(), "cores": psutil.cpu_percent(percpu=True), "mem_total": vm.total, "mem_used":
            vm.total - vm.available, "swap_total": sw.total, "swap_used": sw.used, "rx": net.bytes_recv,
            "tx": net.bytes_sent, "temp": temp, "boot": psutil.boot_time(), "load": os.getloadavg(),
            "host": os.uname().nodename}


def processes(n=6):
    import psutil
    rows = []
    for p in psutil.process_iter(["name", "cpu_percent", "memory_info"]):
        try:
            rows.append({"name": p.info["name"] or "?", "cpu": p.info["cpu_percent"] or 0.0,
                         "rss": p.info["memory_info"].rss if p.info["memory_info"] else 0})
        except Exception:
            continue
    return sorted(rows, key=lambda r: (r["cpu"], r["rss"]), reverse=True)[:n]


def throttled():
    out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=5).stdout
    return {"raw": out}
