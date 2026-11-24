import json, os
from datetime import date

from modules.kev import data

F = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "kev.json")))


def test_newest_first_and_recent_count():
    c = data.parse(F, today=date(2026, 11, 24))
    assert c.recent[0].added >= c.recent[-1].added
    assert c.total >= len(c.recent) and 0 < c.added_30d <= len(c.recent)


def test_ransomware_flag_and_due_date():
    v = data.parse({"vulnerabilities": [{"cveID": "CVE-1", "dateAdded": "2026-01-02", "dueDate": "2026-01-23",
                                          "knownRansomwareCampaignUse": "Known", "vulnerabilityName": "x"}]}).recent[0]
    assert v.ransomware and v.due == date(2026, 1, 23)


def test_bad_rows_skipped_and_empty_raises():
    import pytest
    with pytest.raises(ValueError):
        data.parse({"vulnerabilities": [{"cveID": "CVE-1"}]})


def test_crime_drops_vendor_and_product():
    v = data.Vuln("CVE-1", "Zyxel", "Multiple Products", "Zyxel Multiple Products Use of Hard-Coded Credentials Vulnerability",
                  "", date(2021, 1, 1), None, False)
    assert data.crime(v) == "Use of Hard-Coded Credentials"
