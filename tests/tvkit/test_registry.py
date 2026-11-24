import os

from tvkit import registry

ROOT = os.path.join(os.path.dirname(__file__), "..", "fakemods")


def test_registry_discovers_aliases():
    reg = registry.discover(ROOT, package="tests.fakemods")
    assert reg.get("alpha").name == "alpha" and reg.get("a").name == "alpha"
    assert reg.names() == ["alpha", "beta"]          # ordered by `order`, aliases excluded


def test_registry_skips_broken_module():
    reg = registry.discover(ROOT, package="tests.fakemods")
    assert reg.get("broken") is None and "broken" in reg.errors
