"""python -m tvkit            run the display host (the `tvd` daemon)
python -m tvkit --only NAME   run one module in a window, no socket (development)

Env: TV_WINDOWED=1 (no fullscreen), TV_SNAPSHOT=out.png + TV_SNAPSHOT_AFTER=8 (save a frame, exit).
"""
import argparse, os, signal, sys, time

os.environ.setdefault("SDL_VIDEODRIVER", "wayland")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from . import config as config_mod, control, registry, theme  # noqa: E402
from .host import Host  # noqa: E402

STATE = os.path.expanduser("~/.local/state/pizero-tv/state.json")
CACHE = os.path.expanduser("~/.cache/pizero-tv")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m tvkit")
    ap.add_argument("--only", help="run a single module (dev)")
    args = ap.parse_args(argv)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, root)
    pygame.init()
    flags = pygame.SCALED | pygame.DOUBLEBUF
    if os.environ.get("TV_WINDOWED") != "1":
        flags |= pygame.FULLSCREEN
    screen = pygame.display.set_mode((theme.W, theme.H), flags)
    pygame.display.set_caption("pizero-tv")
    pygame.mouse.set_visible(False)

    cfg = config_mod.load()
    reg = registry.discover()
    host = Host(screen, reg, cfg, state_path=None if args.only else STATE, cache_root=CACHE)
    server = None
    if args.only:
        host.show(args.only)
    else:
        server = control.Server(control.default_path())
        host.resume()

    running = [True]
    signal.signal(signal.SIGTERM, lambda *_: running.__setitem__(0, False))
    snap = os.environ.get("TV_SNAPSHOT")
    snap_after = float(os.environ.get("TV_SNAPSHOT_AFTER", "8"))
    t0 = time.monotonic()
    clock = pygame.time.Clock()
    try:
        while running[0]:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running[0] = False
                elif e.type == pygame.KEYDOWN:
                    if args.only and e.key in (pygame.K_ESCAPE, pygame.K_q):
                        running[0] = False
                    else:
                        host.key(e)
            if server:
                server.poll(host.handle)
            fps = host.step()
            pygame.display.flip()
            if snap and time.monotonic() - t0 > snap_after:
                pygame.image.save(screen, snap)
                break
            clock.tick(fps)
    finally:
        if host.current:
            host.current.stop()
        if server:
            server.close()
        pygame.quit()


if __name__ == "__main__":
    main()
