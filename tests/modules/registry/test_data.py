import gzip, os, shutil, sqlite3

from modules.registry import data


def _faa(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE faa_master (n_number text, serial text, mfr_mdl_code text, year_mfr text, "
                "type_registrant text, name text, street text, street2 text, city text, state text, zip text, "
                "county text, country text, last_action text, cert_issue text, status text, mode_s_hex text, "
                "fract_owner text, other_names text, expiration text, norm_name text)")
    con.execute("CREATE TABLE faa_ref (code text primary key, mfr text, model text, type_acft text, seats text)")
    con.execute("CREATE TABLE faa_meta (key text primary key, value text)")
    con.execute("INSERT INTO faa_master (n_number, mfr_mdl_code, year_mfr, type_registrant, name, street, city, state, "
                "cert_issue, mode_s_hex) VALUES ('905NA', 'B747', '1970', '5', "
                "'NATIONAL AERONAUTICS AND SPACE ADMINISTRATION', '1 SECRET ST', 'HOUSTON', 'TX', '19740917', 'AC82EC')")
    con.execute("INSERT INTO faa_ref VALUES ('B747', 'BOEING', '747-123', '5', '495')")
    con.execute("INSERT INTO faa_meta VALUES ('data_date', '2026-10-28')")
    con.commit()
    con.close()


def test_build_and_lookup_without_street_addresses(tmp_path):
    src, dest = str(tmp_path / "faa.sqlite"), str(tmp_path / "reg" / "registry.sqlite")
    _faa(src)

    def download(to):
        with open(src, "rb") as fi, gzip.open(to, "wb") as fo:
            shutil.copyfileobj(fi, fo)
    meta = data.ensure(dest, download)
    assert meta["rows"] == 1 and meta["date"] == "2026-10-28"
    r = data.lookup(dest, ["ac82ec", "FFFFFF"])["AC82EC"]
    assert r.n == "N905NA" and r.owner_kind == "Government" and r.make == "Boeing" and r.kind == "Multi-engine airplane"
    assert r.since == "09/1974" and r.seats == 495 and r.city == "Houston"
    assert b"SECRET" not in open(dest, "rb").read()                       # no street addresses kept
    assert not [p for p in os.listdir(tmp_path / "reg") if p.endswith((".gz", ".src"))]


def test_fresh_file_is_not_downloaded_again(tmp_path):
    src, dest = str(tmp_path / "faa.sqlite"), str(tmp_path / "r.sqlite")
    _faa(src)
    data.build(src, dest)
    calls = []
    data.ensure(dest, lambda to: calls.append(to))
    assert calls == []


def test_nice_names():
    assert data.nice("LITTLE GATOR AVIATION INC") == "Little Gator Aviation Inc"
    assert data.nice("SKYWEST AIRLINES LLC") == "Skywest Airlines LLC"
    assert data.nice("WELLS FARGO TRUST CO NA TRUSTEE") == "Wells Fargo Trust Co NA Trustee"
