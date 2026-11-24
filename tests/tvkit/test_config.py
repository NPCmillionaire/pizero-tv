from tvkit import config


def test_config_missing_file_defaults(tmp_path):
    c = config.load(str(tmp_path / "nope.toml"))
    assert c.place is None and c.units_temp == "F" and c.cycle_seconds == 90
    assert c.lan_subnet is None and c.cycle_modules is None


def test_config_reads_place(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[place]\nname = "San Francisco"\nlat = 37.77\nlon = -122.42\n'
                 'timezone = "America/Los_Angeles"\n[units]\ntemp = "C"\n[lan]\nsubnet = "10.0.0.0/24"\n'
                 '[cycle]\nseconds = 45\nmodules = ["weather", "crypto"]\n')
    c = config.load(str(p))
    assert c.place.name == "San Francisco" and c.place.lat == 37.77 and c.place.lon == -122.42
    assert c.place.timezone == "America/Los_Angeles" and c.units_temp == "C"
    assert c.lan_subnet == "10.0.0.0/24" and c.cycle_seconds == 45 and c.cycle_modules == ["weather", "crypto"]


def test_config_bad_toml_falls_back_to_defaults(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text("[place\nname=")
    assert config.load(str(p)).place is None


def test_example_config_parses():
    import os
    c = config.load(os.path.join(os.path.dirname(__file__), "..", "..", "config.example.toml"))
    assert c.place.name == "San Francisco"
