"""The Module API every screen implements. See the suite design doc."""
import os, time
from dataclasses import dataclass

from . import theme
from .source import Source


@dataclass
class Ctx:
    config: object
    cache_dir: str | None
    w: int = theme.W
    h: int = theme.H
    fakes: dict | None = None   # tests: {source name: payload, "__mode__": waiting|live|stale|offline}
    registry: object = None     # the host's channel list (the guide reads it)


class Module:
    name = ""
    title = ""            # spine text, one word, caps
    blurb = ""            # one line for the guide
    key = theme.SODIUM    # spine / accent color
    aliases = ()
    order = 100           # position in the default cycle
    fps = 24              # frame rate while draw_live reports motion
    resume = True         # False: never reopened by a restarted host (video players)
    footer_color = None   # station bug color over this channel's background (None: theme default)

    def __init__(self):
        self.sources = []
        self.ctx = None
        self.dirty = True
        self._seen = None

    # lifecycle ------------------------------------------------------------
    def start(self, ctx):
        self.ctx = ctx

    def stop(self):
        """Signal every source, then give them all one short shared deadline (threads are daemons)."""
        for s in self.sources:
            s.signal_stop()
        deadline = time.monotonic() + 0.5
        for s in self.sources:
            s.stop(timeout=max(0.0, deadline - time.monotonic()))
        self.sources = []

    def source(self, name, fetch, interval, parse=lambda x: x, cache=True):
        """Register a polled Source (started immediately on its own thread)."""
        fakes = self.ctx.fakes if self.ctx else None
        if fakes is not None:
            return self._fake_source(name, interval, parse, fakes)
        cache_dir = self.ctx.cache_dir if (cache and self.ctx and self.ctx.cache_dir) else None
        s = Source(name, fetch, interval, parse=parse, cache_dir=cache_dir)
        self.sources.append(s)
        return s.start()

    def _fake_source(self, name, interval, parse, fakes):
        mode, payload = fakes.get("__mode__", "live"), fakes.get(name)

        def fetch():
            if mode == "offline" or payload is None:
                raise ConnectionError("fake offline")
            return payload
        s = Source(name, fetch, interval, parse=parse)
        self.sources.append(s)
        if mode in ("live", "stale", "offline"):
            s.poll_once()
        if mode == "stale":
            s._last_ok = False
        return s

    # host hooks -----------------------------------------------------------
    def draw_frame(self, surf):
        """The channel's backdrop, drawn under draw_static. Default: the house spine frame."""
        from . import chrome
        chrome.draw_frame(surf, chrome.spine(self.title, self.key))

    @property
    def ready(self):
        return all(s.status != "waiting" for s in self.sources)

    def update(self, now):
        """Return True when the static layer must be redrawn."""
        seen = tuple((s.version, s.status) for s in self.sources)
        changed = seen != self._seen or self.dirty
        self._seen, self.dirty = seen, False
        return changed

    def draw_static(self, surf):
        pass

    def draw_live(self, surf, t):
        """Draw animation over the static layer. Return True while animating."""
        return False

    def on_key(self, event):
        pass

    def status(self):
        """Worst status across sources, for the footer: (status, age_s) or (None, None)."""
        if not self.sources:
            return None, None
        for st in ("offline", "stale", "waiting"):
            hit = [s for s in self.sources if s.status == st]
            if hit:
                ages = [s.age_s for s in hit if s.age_s is not None]
                return st, (max(ages) if ages else None)
        return "live", None
