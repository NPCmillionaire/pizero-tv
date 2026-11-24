import json, os

import pytest

from modules.threatmap import data

D = os.path.join(os.path.dirname(__file__), "fixtures")
L = lambda n: json.load(open(os.path.join(D, n + ".json")))


def test_parse_attackers_joins_geo():
    a = data.parse_attackers(L("attackers"))
    assert len(a) == 40
    top = a[0]
    assert top.ip == "77.239.124.252" and top.cc == "FR" and top.country == "France"
    assert top.reports == 1454918 and top.targets == 385 and top.lat is not None


def test_parse_attackers_tolerates_failed_geo():
    p = L("attackers")
    p["geo"][0] = {"status": "fail", "query": p["attacks"][0]["ip"]}
    a = data.parse_attackers(p)
    assert a[0].lat is None and a[0].cc is None and len(a) == 40


def test_parse_ports_with_service_names():
    ports = data.parse_ports(L("ports"))
    assert ports[0].port == 22 and ports[0].service == "SSH" and ports[0].records == 13154
    assert [p.rank for p in ports] == sorted(p.rank for p in ports)


@pytest.mark.parametrize("port,name", [(23, "Telnet"), (3389, "Remote Desktop"), (445, "Windows file sharing"),
                                       (16767, None)])
def test_service_names(port, name):
    assert data.service(port) == name


def test_parse_infocon():
    assert data.parse_infocon(L("infocon")) == "green"
    with pytest.raises(ValueError):
        data.parse_infocon({"status": "plaid"})


def test_parse_feodo_counts_online():
    c2 = data.parse_feodo(L("feodo"))
    assert len(c2) == 5 and sum(1 for x in c2 if x.online) == 1


def test_by_country():
    rows = data.by_country(data.parse_attackers(L("attackers")))
    assert rows[0][0] == "BE" and rows[0][2] == 18
    assert sum(r[2] for r in rows) == 40
