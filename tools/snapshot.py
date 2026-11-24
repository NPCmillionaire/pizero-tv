#!/usr/bin/env python3
"""Render a channel from its test fixtures to a PNG (no network, no display).

    .venv/bin/python tools/snapshot.py weather out.png [seconds]
"""
import os, sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from tests.modules.test_render_smoke import PLACE, fixtures  # noqa: E402
from tvkit import chrome, registry, text  # noqa: E402
from tvkit.module import Ctx  # noqa: E402


def main(name, out, t=2.0):
    pygame.init()
    pygame.display.set_mode((1, 1))
    cls = registry.discover().get(name)
    m = cls()
    m.start(Ctx(PLACE, None, fakes=fixtures(cls.name)))
    surf = pygame.Surface((1280, 720))
    m.update(0.0)
    m.draw_frame(surf)
    m.draw_static(surf)
    chrome.draw_footer(surf, *m.status(), color=m.footer_color)
    for k in range(1, 6):
        m.draw_live(surf, t * k / 5)
    pygame.image.save(surf, out)
    m.stop()
    if text.OVERFLOWS:
        print("overflows:", text.OVERFLOWS)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 2.0)
