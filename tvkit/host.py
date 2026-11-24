"""The display host: one window, one module at a time, splash in between."""
import json, os, sys, time, traceback

import pygame

from . import chrome, scenes
from .module import Ctx

SPLASH_MIN, READY_MAX, CRASH_S = 1.2, 8.0, 10.0
FPS_ACTIVE, FPS_IDLE = 24, 8


class Host:
    def __init__(self, screen, registry, config, state_path=None, cache_root=None,
                 clock=time.monotonic):
        self.screen, self.registry, self.config = screen, registry, config
        self.state_path, self.cache_root, self.clock = state_path, cache_root, clock
        self.static = pygame.Surface(screen.get_size()).convert() if pygame.display.get_init() \
            and pygame.display.get_surface() else pygame.Surface(screen.get_size())
        self.current, self.cls = None, None
        self.phase, self.mode = "standby", "standby"
        self.cycle_seconds, self.cycle_names = config.cycle_seconds, None
        self.t_phase = self.t_shown = clock()
        self.crash_text, self.crash_name = "", ""
        self._footer = None
        self._standby_min = None

    # -- commands ------------------------------------------------------------
    def show(self, name, mode="show"):
        cls = self.registry.get(name)
        if cls is None:
            raise KeyError(name)
        self._stop_current()
        self.cls, self.mode = cls, mode
        self.phase, self.t_phase = "splash", self.clock()
        self._footer = None
        try:
            self.current = cls()
            cache = os.path.join(self.cache_root, cls.name) if self.cache_root else None
            self.current.start(Ctx(self.config, cache))
        except Exception:
            self._crash(traceback.format_exc())
        self._save()

    def cycle(self, seconds=None, names=None, start=None):
        self.cycle_seconds = int(seconds or self.config.cycle_seconds)
        self.cycle_names = [n for n in names if self.registry.get(n)] if names else None
        order = self._order()
        if order:
            self.show(start if start in order else order[0], mode="cycle")

    def next(self):
        order = self._order()
        if not order:
            return self.standby()
        cur = self.cls.name if self.cls else None
        i = order.index(cur) + 1 if cur in order else 0
        self.show(order[i % len(order)], mode=self.mode if self.mode == "cycle" else "show")

    def standby(self):
        self._stop_current()
        self.cls, self.phase, self.mode = None, "standby", "standby"
        self._standby_min = None
        self._save()

    def resume(self):
        st = {}
        if self.state_path and os.path.exists(self.state_path):
            try:
                st = json.load(open(self.state_path))
            except Exception:
                st = {}
        mode, name = st.get("mode"), st.get("module")
        if mode == "standby":
            return self.standby()
        if mode == "show" and self.registry.get(name):
            return self.show(name)
        if mode == "cycle" and (name is None or self.registry.get(name)):
            return self.cycle(st.get("cycle_seconds"), st.get("cycle_names"), start=name)
        self.cycle(self.config.cycle_seconds, self.config.cycle_modules)

    def handle(self, line):
        parts = line.split()
        if not parts:
            return "error: empty command"
        cmd, args = parts[0], parts[1:]
        try:
            if cmd == "show" and args:
                self.show(args[0])
            elif cmd == "next":
                self.next()
            elif cmd == "cycle":
                secs = int(args[0]) if args and args[0].isdigit() else None
                self.cycle(secs, args[1:] if secs else args or None)
            elif cmd == "stop":
                self.standby()
            elif cmd == "reload" and self.cls:
                self.show(self.cls.name, mode=self.mode)
            elif cmd == "screenshot" and args:
                pygame.image.save(self.screen, args[0])
            elif cmd == "status":
                return json.dumps(self.status())
            elif cmd == "list":
                return json.dumps([{"name": c.name, "title": c.title, "blurb": c.blurb, "aliases": list(c.aliases)}
                                   for c in self.registry.classes()])
            else:
                return f"error: unknown command {line}"
        except KeyError as e:
            return f"error: unknown module {e.args[0]}"
        return "ok"

    def status(self):
        st, age = self.current.status() if (self.current and self.phase == "module") else (None, None)
        return {"mode": self.mode, "phase": self.phase, "module": self.cls.name if self.cls else None,
                "since_s": round(self.clock() - self.t_phase, 1), "cycle_seconds": self.cycle_seconds,
                "cycle_names": self.cycle_names, "data": st, "data_age_s": age}

    def key(self, event):
        if self.current and self.phase == "module":
            try:
                self.current.on_key(event)
            except Exception:
                self._crash(traceback.format_exc())

    # -- frame ---------------------------------------------------------------
    def step(self):
        now = self.clock()
        if self.phase == "splash":
            elapsed = now - self.t_phase
            ready = self._safe(lambda: self.current.ready, default=True) if self.current else True
            if elapsed >= SPLASH_MIN and (ready or elapsed >= READY_MAX):
                self.phase, self.t_shown = "module", now
                self.current.dirty = True
            else:
                scenes.splash(self.screen, self.cls, elapsed)
                return FPS_ACTIVE
        if self.phase == "module":
            if self.mode == "cycle" and now - self.t_shown >= self.cycle_seconds:
                self.next()
                return FPS_ACTIVE
            try:
                self._draw_module(now)
                return FPS_ACTIVE if self.current.draw_live(self.screen, now) else FPS_IDLE
            except Exception:
                self._crash(traceback.format_exc())
        if self.phase == "crash":
            left = CRASH_S - (now - self.t_phase)
            if left <= 0:
                return self.next() or FPS_ACTIVE if self.mode == "cycle" else self.standby() or FPS_IDLE
            scenes.crash(self.screen, self.crash_name, self.crash_text, left)
            return FPS_IDLE
        # standby: redraw once a minute
        minute = time.strftime("%H:%M")
        if minute != self._standby_min:
            scenes.standby(self.screen)
            self._standby_min = minute
        return 2

    def _draw_module(self, now):
        m = self.current
        changed = m.update(now)
        footer = m.status()
        if changed or footer != self._footer:
            chrome.draw_frame(self.static, chrome.spine(m.title, m.key))
            m.draw_static(self.static)
            chrome.draw_footer(self.static, *footer)
            self._footer = footer
        self.screen.blit(self.static, (0, 0))

    # -- helpers -------------------------------------------------------------
    def _order(self):
        return self.cycle_names or self.registry.names()

    def _safe(self, fn, default=None):
        try:
            return fn()
        except Exception:
            self._crash(traceback.format_exc())
            return default

    def _crash(self, tb):
        print(tb, file=sys.stderr, flush=True)
        last = [l for l in tb.strip().splitlines() if l.strip()]
        self.crash_text = last[-1] if last else "unknown error"
        self.crash_name = self.cls.name if self.cls else "module"
        self._stop_current(keep_cls=True)
        self.phase, self.t_phase = "crash", self.clock()

    def _stop_current(self, keep_cls=False):
        if self.current is not None:
            try:
                self.current.stop()
            except Exception:
                traceback.print_exc()
        self.current = None
        if not keep_cls:
            self.cls = None

    def _save(self):
        if not self.state_path:
            return
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            with open(self.state_path, "w") as fh:
                json.dump({"mode": self.mode, "module": self.cls.name if self.cls else None,
                           "cycle_seconds": self.cycle_seconds, "cycle_names": self.cycle_names}, fh)
        except Exception:
            traceback.print_exc()
