import json, threading, urllib.request

from tvkit import agent


def test_cpu_percent_from_two_proc_stat_samples():
    a = agent.parse_proc_stat("cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 1 2 3 4\n")
    b = agent.parse_proc_stat("cpu  150 0 150 900 0 0 0 0 0 0\n")
    assert a == (200, 1000)
    assert agent.cpu_pct(a, b) == 50.0
    assert agent.cpu_pct(None, b) is None


def test_meminfo_uses_available_memory():
    total, used = agent.parse_meminfo("MemTotal:  1000 kB\nMemFree:  100 kB\nMemAvailable:  400 kB\n")
    assert (total, used) == (1000 * 1024, 600 * 1024)


def test_vm_stat_counts_active_wired_and_compressed():
    raw = ("Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free:  10.\nPages active:  100.\n"
           "Pages inactive:  50.\nPages wired down:  20.\nPages occupied by compressor:  5.\n")
    assert agent.parse_vm_stat(raw, 10 ** 12) == 125 * 16384


def test_boottime():
    assert agent.parse_boottime("{ sec = 1764000000, usec = 1 } Mon Nov 24") == 1764000000


def test_net_dev_skips_loopback_and_docker():
    raw = ("Inter-|   Receive\n face |bytes\n    lo: 999 0 0 0 0 0 0 0 999 0\n"
           "  eth0: 100 1 0 0 0 0 0 0 200 1\ndocker0: 50 0 0 0 0 0 0 0 50 0\n")
    assert agent.parse_net_dev(raw) == (100, 200)


def test_netstat_ib_sums_link_rows_of_real_interfaces():
    raw = ("Name       Mtu   Network       Address            Ipkts Ierrs     Ibytes    Opkts Oerrs     Obytes  Coll\n"
           "lo0        16384 <Link#1>                          10     0       999       10     0       999     0\n"
           "en0        1500  <Link#11>   aa:bb:cc:dd:ee:ff    100     0       500      100     0       700     0\n"
           "en0        1500  192.168.8     192.168.8.238       100     -       500      100     -       700     -\n")
    assert agent.parse_netstat_ib(raw) == (500, 700)


def test_only_private_networks_may_ask():
    assert agent.allowed("192.168.8.50") and agent.allowed("127.0.0.1") and agent.allowed("10.0.0.2")
    assert not agent.allowed("8.8.8.8") and not agent.allowed("nonsense")


def test_serves_stats_json():
    from http.server import ThreadingHTTPServer
    s = agent.Sampler()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), agent.make_handler(s))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        body = json.load(urllib.request.urlopen(f"http://127.0.0.1:{srv.server_port}/stats", timeout=10))
        assert body["cores"] >= 1 and body["mem_total"] > 0 and body["host"]
    finally:
        srv.shutdown()
