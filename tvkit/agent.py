"""pizero-tv stats agent: a tiny read-only HTTP endpoint so the SYSTEM channel can show other machines.

    python3 agent.py [--port 8765]        then   curl http://host:8765/stats

Standard library only (runs on macOS's /usr/bin/python3 3.9 and any Linux). It answers GET /stats with
processor, memory, disk, uptime, temperature and network counters, and refuses anyone outside private
network ranges. It never accepts input beyond the request path.
"""
import ipaddress, json, os, platform, re, shutil, socket, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765
SAMPLE_S = 3


# -- parsers (pure, tested) -------------------------------------------------------
def parse_proc_stat(raw):
    """/proc/stat first line → (busy, total) jiffies."""
    f = [int(x) for x in raw.splitlines()[0].split()[1:]]
    idle = f[3] + (f[4] if len(f) > 4 else 0)
    return sum(f) - idle, sum(f)


def cpu_pct(prev, cur):
    if prev is None:
        return None
    db, dt = cur[0] - prev[0], cur[1] - prev[1]
    return round(100.0 * db / dt, 1) if dt > 0 else 0.0


def parse_meminfo(raw):
    kv = {}
    for line in raw.splitlines():
        k, _, v = line.partition(":")
        if v.strip():
            kv[k] = int(v.split()[0]) * 1024
    total = kv.get("MemTotal", 0)
    return total, total - kv.get("MemAvailable", kv.get("MemFree", 0))


def parse_vm_stat(raw, total):
    """macOS vm_stat → bytes in use (active + wired + compressed), the way Activity Monitor counts it."""
    m = re.search(r"page size of (\d+) bytes", raw)
    page = int(m.group(1)) if m else 4096
    pages = {}
    for line in raw.splitlines()[1:]:
        k, _, v = line.partition(":")
        v = v.strip().rstrip(".")
        if v.isdigit():
            pages[k.strip()] = int(v)
    used = sum(pages.get(k, 0) for k in ("Pages active", "Pages wired down", "Pages occupied by compressor"))
    return min(total, used * page)


def parse_boottime(raw):
    """sysctl kern.boottime → epoch seconds."""
    m = re.search(r"sec = (\d+)", raw)
    return int(m.group(1)) if m else None


def parse_net_dev(raw):
    """/proc/net/dev → total (rx, tx) bytes, ignoring loopback and virtual bridges."""
    rx = tx = 0
    for line in raw.splitlines()[2:]:
        name, _, rest = line.partition(":")
        name = name.strip()
        if name == "lo" or name.startswith(("docker", "veth", "br-", "virbr")):
            continue
        f = rest.split()
        if len(f) >= 9:
            rx, tx = rx + int(f[0]), tx + int(f[8])
    return rx, tx


def parse_netstat_ib(raw):
    """macOS `netstat -ib` → total (rx, tx) bytes over the link-layer rows of real interfaces."""
    rx = tx = 0
    lines = raw.splitlines()
    if not lines:
        return None
    head = lines[0].split()
    try:
        ib, ob = head.index("Ibytes"), head.index("Obytes")
    except ValueError:
        return None
    for line in lines[1:]:
        f = line.split()
        if len(f) < len(head) or not f[2].startswith("<Link"):
            continue
        if f[0].startswith(("lo", "utun", "awdl", "llw", "bridge", "gif", "stf", "anpi", "ap")):
            continue
        rx, tx = rx + int(f[ib]), tx + int(f[ob])
    return rx, tx


# -- collection ---------------------------------------------------------------------
def _read(path):
    with open(path) as fh:
        return fh.read()


def _run(*argv):
    return subprocess.run(argv, capture_output=True, text=True, timeout=10).stdout


def _linux_temp():
    best = None
    for root, names in (("/sys/class/hwmon", None),):
        if not os.path.isdir(root):
            continue
        for d in os.listdir(root):
            p = os.path.join(root, d)
            try:
                name = _read(os.path.join(p, "name")).strip()
            except OSError:
                continue
            if name in ("coretemp", "k10temp", "cpu_thermal", "zenpower", "acpitz"):
                for f in sorted(os.listdir(p)):
                    if f.startswith("temp") and f.endswith("_input"):
                        try:
                            t = int(_read(os.path.join(p, f))) / 1000
                        except (OSError, ValueError):
                            continue
                        best = t if best is None else max(best, t)
                if best is not None:
                    return round(best, 1)
    try:
        return round(int(_read("/sys/class/thermal/thermal_zone0/temp")) / 1000, 1)
    except (OSError, ValueError):
        return None


class Sampler:
    def __init__(self):
        self.mac = sys.platform == "darwin"
        self.prev_cpu, self.cpu = None, None
        self.lock = threading.Lock()

    def sample_cpu(self):
        if self.mac:
            out = _run("ps", "-A", "-o", "%cpu=")
            total = sum(float(x) for x in out.split() if re.match(r"^[\d.]+$", x))
            with self.lock:
                self.cpu = round(min(100.0, total / (os.cpu_count() or 1)), 1)
            return
        cur = parse_proc_stat(_read("/proc/stat"))
        with self.lock:
            pct = cpu_pct(self.prev_cpu, cur)
            self.prev_cpu = cur
            if pct is not None:
                self.cpu = pct

    def loop(self):
        while True:
            try:
                self.sample_cpu()
            except Exception as ex:          # keep serving the rest
                print("cpu sample failed:", ex, file=sys.stderr)
            time.sleep(SAMPLE_S)

    def snapshot(self):
        disk = shutil.disk_usage("/System/Volumes/Data" if self.mac and os.path.isdir("/System/Volumes/Data") else "/")
        out = {"host": socket.gethostname().split(".")[0], "os": platform.system(),
               "os_release": platform.mac_ver()[0] if self.mac else platform.release(),
               "cores": os.cpu_count(), "load": list(os.getloadavg()), "disk_total": disk.total,
               "disk_used": disk.used, "time": time.time()}
        with self.lock:
            out["cpu"] = self.cpu
        if self.mac:
            total = int(_run("sysctl", "-n", "hw.memsize").strip() or 0)
            out["mem_total"], out["mem_used"] = total, parse_vm_stat(_run("vm_stat"), total)
            out["boot"] = parse_boottime(_run("sysctl", "-n", "kern.boottime"))
            out["model"] = _run("sysctl", "-n", "machdep.cpu.brand_string").strip() or None
            out["temp"] = None
            net = parse_netstat_ib(_run("netstat", "-ib"))
        else:
            out["mem_total"], out["mem_used"] = parse_meminfo(_read("/proc/meminfo"))
            out["boot"] = time.time() - float(_read("/proc/uptime").split()[0])
            m = re.search(r"model name\s*:\s*(.+)", _read("/proc/cpuinfo"))
            out["model"] = m.group(1).strip() if m else None
            out["temp"] = _linux_temp()
            net = parse_net_dev(_read("/proc/net/dev"))
        out["net_rx"], out["net_tx"] = net if net else (None, None)
        return out


def allowed(addr):
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback


def make_handler(sampler):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if not allowed(self.client_address[0]):
                return self._send(403, {"error": "private networks only"})
            if self.path.split("?")[0] != "/stats":
                return self._send(404, {"error": "try /stats"})
            try:
                self._send(200, sampler.snapshot())
            except Exception as ex:
                self._send(500, {"error": str(ex)})

        def _send(self, code, body):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass
    return Handler


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="pizero-tv stats agent")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--bind", default="0.0.0.0")
    args = ap.parse_args(argv)
    s = Sampler()
    threading.Thread(target=s.loop, daemon=True).start()
    ThreadingHTTPServer((args.bind, args.port), make_handler(s)).serve_forever()


if __name__ == "__main__":
    main()
