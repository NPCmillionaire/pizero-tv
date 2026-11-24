"""The display host: one window, one module at a time, channel static in between."""
import json, os, sys, time, traceback

import pygame

from . import chrome, scenes, text
from .module import Ctx

STATIC_S, CRASH_S, OSD_S, OSD_FADE, DIGIT_S = 0.4, 10.0, 3.0, 0.5, 1.2
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
        self.osd_t = -1e9
        self._digits, self._digit_t = "", None

    # -- commands ------------------------------------------------------------
    def show(self, name, mode="show"):
        cls = self.registry.get(name)
        if cls is None:
            raise KeyError(name)
        self._stop_current()
        text.clear_cache()
        self.cls, self.mode = cls, mode
        self.phase, self.t_phase = "static", self.clock()
        self.osd_t = self.t_phase
        self._footer = None
        try:
            self.current = cls()
            cache = os.path.join(self.cache_root, cls.name) if self.cache_root else None
            self.current.start(Ctx(self.config, cache, registry=self.registry))
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
        if order == [cur] and self.current is not None and self.phase == "module":
            self.t_shown = self.clock()       # nothing to rotate to: keep it running
            return
        i = order.index(cur) + 1 if cur in order else 0
        self.show(order[i % len(order)], mode=self.mode if self.mode == "cycle" else "show")

    def channel(self, n):
        chans = self.registry.channels()
        if not 0 <= n < len(chans):
            raise IndexError(n)
        self.show(chans[n].name, mode="show")

    def _step_channel(self, delta):
        chans = self.registry.channels()
        if not chans:
            return
        cur = self.registry.number(self.cls.name) if self.cls else -delta
        self.channel(((cur if cur is not None else 0) + delta) % len(chans))

    def up(self):
        self._step_channel(1)

    def down(self):
        self._step_channel(-1)

    def digit(self, d):
        """Remote-style entry: two digits within DIGIT_S make one channel number."""
        self._digits += str(d)
        self._digit_t = self.clock()
        if len(self._digits) >= 2:
            self._commit_digits()

    def _commit_digits(self):
        n, self._digits, self._digit_t = int(self._digits), "", None
        try:
            self.channel(n)
        except IndexError:
            pass

    def osd_alpha(self, now):
        e = now - self.osd_t
        if e <= OSD_S:
            return 255
        return max(0, int(255 * (1 - (e - OSD_S) / OSD_FADE)))

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
            elif cmd == "up":
                self.up()
            elif cmd == "down":
                self.down()
            elif cmd == "digit" and args and args[0].isdigit() and len(args[0]) == 1:
                self.digit(int(args[0]))
            elif cmd == "ch" and args and args[0].isdigit():
                try:
                    self.channel(int(args[0]))
                except IndexError:
                    return f"error: no channel {args[0]}"
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
                return json.dumps([{"ch": i, "name": c.name, "title": c.title, "blurb": c.blurb,
                                    "aliases": list(c.aliases)} for i, c in enumerate(self.registry.channels())])
            else:
                return f"error: unknown command {line}"
        except KeyError as e:
            return f"error: unknown module {e.args[0]}"
        return "ok"

    def status(self):
        st, age = self.current.status() if (self.current and self.phase == "module") else (None, None)
        return {"mode": self.mode, "phase": self.phase, "module": self.cls.name if self.cls else None,
                "channel": self.registry.number(self.cls.name) if self.cls else None,
                "since_s": round(self.clock() - self.t_phase, 1), "cycle_seconds": self.cycle_seconds,
                "cycle_names": self.cycle_names, "data": st, "data_age_s": age}

    def key(self, event):
        k = event.key
        if k in (pygame.K_UP, pygame.K_PAGEUP):
            return self.up()
        if k in (pygame.K_DOWN, pygame.K_PAGEDOWN):
            return self.down()
        if pygame.K_0 <= k <= pygame.K_9:
            return self.digit(k - pygame.K_0)
        if self.current and self.phase == "module":
            try:
                self.current.on_key(event)
            except Exception:
                self._crash(traceback.format_exc())

    # -- frame ---------------------------------------------------------------
    def step(self):
        now = self.clock()
        if self._digit_t is not None and now - self._digit_t >= DIGIT_S:
            self._commit_digits()
        if self.phase == "static":
            elapsed = now - self.t_phase
            if elapsed < STATIC_S:
                scenes.static(self.screen, elapsed)
                return FPS_ACTIVE
            self.phase, self.t_shown = "module", now
            if self.current:
                self.current.dirty = True
        if self.phase == "module":
            if self.mode == "cycle" and now - self.t_shown >= self.cycle_seconds:
                self.next()
                return FPS_ACTIVE
            if getattr(self.current, "external", False):
                return 2                      # an external player owns the screen
            try:
                self._draw_module(now)
                moving = self.current.draw_live(self.screen, now)
            except Exception:
                self._crash(traceback.format_exc())
                return FPS_IDLE
            a = self.osd_alpha(now)
            if a:
                scenes.osd(self.screen, self.registry.number(self.cls.name), self.cls.title, a)
            if 0 < a < 255:
                return FPS_ACTIVE
            return getattr(self.current, "fps", FPS_ACTIVE) if moving else FPS_IDLE
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
