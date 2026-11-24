"""A polled data source with a last-good disk cache and an honest status."""
import json, os, sys, threading, time

STALE_INTERVALS = 3


class Source:
    """Calls fetch() every `interval` seconds on a thread; parse() turns the raw payload
    into the value modules read. Exceptions never escape: the status says what happened.

    status: waiting (nothing yet) · live · stale (old, cached, or last refresh failed) · offline
    """

    def __init__(self, name, fetch, interval, parse=lambda x: x, cache_dir=None,
                 clock=time.monotonic, wall=time.time):
        self.name, self.fetch, self.interval, self.parse = name, fetch, interval, parse
        self.clock, self.wall = clock, wall
        self.cache_path = os.path.join(cache_dir, f"{name}.json") if cache_dir else None
        self.value, self.version = None, 0
        self._got_at = None          # wall time of the last good payload
        self._last_ok = None         # did the most recent attempt succeed?
        self._from_cache = False
        self._stop = threading.Event()
        self._thread = None
        self._load_cache()

    # -- cache ---------------------------------------------------------------
    def _load_cache(self):
        if not self.cache_path or not os.path.exists(self.cache_path):
            return
        try:
            with open(self.cache_path) as fh:
                blob = json.load(fh)
            self.value = self.parse(blob["payload"])
            self._got_at, self._from_cache, self.version = blob["at"], True, 1
        except Exception:
            self.value = None

    def _save_cache(self, payload):
        if not self.cache_path:
            return
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            tmp = self.cache_path + ".tmp"
            with open(tmp, "w") as fh:
                json.dump({"at": self._got_at, "payload": payload}, fh)
            os.replace(tmp, self.cache_path)
        except Exception as e:  # cache is best effort
            print(f"[{self.name}] cache write failed: {e!r}", file=sys.stderr)

    # -- polling -------------------------------------------------------------
    def poll_once(self):
        try:
            payload = self.fetch()
            value = self.parse(payload)
        except Exception as e:
            print(f"[{self.name}] {type(e).__name__}: {e}", file=sys.stderr)
            self._last_ok = False
            return False
        self.value, self._got_at, self._last_ok, self._from_cache = value, self.wall(), True, False
        self.version += 1
        self._save_cache(payload)
        return True

    def _run(self):
        while not self._stop.is_set():
            self.poll_once()
            self._stop.wait(self.interval)

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name=f"source:{self.name}", daemon=True)
            self._thread.start()
        return self

    def stop(self, timeout=2.0):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None

    # -- status --------------------------------------------------------------
    @property
    def age_s(self):
        return None if self._got_at is None else max(0.0, self.wall() - self._got_at)

    @property
    def status(self):
        if self.value is None:
            return "offline" if self._last_ok is False else "waiting"
        if self._from_cache or self._last_ok is False or self.age_s > STALE_INTERVALS * self.interval:
            return "stale"
        return "live"
