"""Every module draws every data state without crashing or spilling text off screen."""
import glob, json, os

import pygame
import pytest

from tvkit import chrome, config, registry, text
from tvkit.module import Ctx

HERE = os.path.dirname(__file__)
REG = registry.discover()
MODES = ["waiting", "live", "stale", "offline"]
PLACE = config.Config(place=config.Place("San Francisco", 37.7749, -122.4194, "America/Los_Angeles"),
                      lan_subnet="192.168.1.0/24")


def fixtures(name):
    out = {}
    for p in glob.glob(os.path.join(HERE, name, "fixtures", "*.json")):
        out[os.path.splitext(os.path.basename(p))[0]] = json.load(open(p))
    return out


def render(cls, fakes, cfg=PLACE):
    m = cls()
    m.start(Ctx(cfg, None, fakes=fakes))
    surf = pygame.Surface((1280, 720))
    try:
        m.draw_frame(surf)
        m.update(0.0)
        m.draw_static(surf)
        chrome.draw_footer(surf, *m.status(), color=m.footer_color)
        for t in (0.05, 0.5, 1.0, 2.5):
            m.draw_live(surf, t)
    finally:
        m.stop()
    return surf


@pytest.mark.parametrize("name", REG.names())
@pytest.mark.parametrize("mode", MODES)
def test_render_smoke(name, mode):
    text.OVERFLOWS.clear()
    fakes = fixtures(name)
    fakes["__mode__"] = mode
    render(REG.get(name), fakes)
    assert text.OVERFLOWS == []


@pytest.mark.parametrize("name", REG.names())
def test_render_without_config(name):
    text.OVERFLOWS.clear()
    fakes = fixtures(name)
    render(REG.get(name), fakes, cfg=config.Config())
    assert text.OVERFLOWS == []


def test_registry_has_no_import_errors():
    assert REG.errors == {}
