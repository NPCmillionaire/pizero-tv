"""Video channels: YouTube played full screen by mpv. COMPUTERPHILE, SHORTS, and any [[video]] in config."""
import json, os, shutil, subprocess, sys, threading, time

from tvkit import ORPHAN_MPV, config as config_mod, text, theme
from tvkit.module import Module

from . import data

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TV = os.path.join(ROOT, "bin", "tv")
LISTING_S = 6 * 3600
ORPHAN_PATTERN = ORPHAN_MPV
X0 = 190
DEFAULT_SHORTS = ["@veritasium", "@minutephysics", "@SteveMould", "@TheActionLab", "@NileRed"]   # all have Shorts tabs


def oom_adj_path(pid):
    return f"/proc/{pid}/oom_score_adj"


def ytdlp_path():
    local = os.path.expanduser("~/.local/bin/yt-dlp")
    return local if os.access(local, os.X_OK) else shutil.which("yt-dlp")


def fetch_listing(urls, stop=None, per=15):
    """List uploads for each URL with yt-dlp. Stops (and kills yt-dlp) as soon as `stop` is set."""
    ytdl = ytdlp_path()
    if not ytdl:
        raise RuntimeError("yt-dlp is not installed")
    # one yt-dlp run for every URL: on a Pi Zero, yt-dlp's own startup is most of the cost
    p = subprocess.Popen(["nice", "-n", "15", ytdl, "--flat-playlist", "-J", "--ignore-errors", "--playlist-end", str(per), *urls],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    deadline = time.monotonic() + 900                     # a busy, swapping Pi Zero can be slow
    while True:
        try:
            out, _ = p.communicate(timeout=1)
            break
        except subprocess.TimeoutExpired:
            if (stop is not None and stop.is_set()) or time.monotonic() > deadline:
                p.kill()
                p.communicate()
                raise RuntimeError("listing interrupted")
    entries = data.parse_json_lines(out)
    return {"entries": [{k: e.get(k) for k in ("id", "title", "duration", "url")} for e in entries if e]}


class VideoChannel(Module):
    urls = ()
    order = 100
    fps = 8
    resume = False

    def start(self, ctx):
        super().start(ctx)
        self.recent, self.now_playing, self.problem = [], None, None
        self.proc, self._stop, self._lock = None, threading.Event(), threading.Lock()
        self.input_conf = os.path.join(ctx.cache_dir or "/tmp/pizero-tv", "mpv-input.conf")
        self.listing = self.source("listing", lambda: fetch_listing(self.urls, self._stop), LISTING_S,
                                   parse=data.parse_listing)
        if not shutil.which("mpv"):
            self.problem = "This channel needs mpv. Install it with: sudo apt install mpv"
            return
        if not ytdlp_path():
            self.problem = ("This channel needs a current yt-dlp in ~/.local/bin or on the PATH. "
                            "See the README's video section.")
            return
        if ctx.fakes is not None:
            return                                   # tests: never launch a real player
        self._thread = threading.Thread(target=self._player, name=f"player:{self.name}", daemon=True)
        self._thread.start()

    # -- player loop ---------------------------------------------------------------
    def _player(self):
        os.makedirs(os.path.dirname(self.input_conf), exist_ok=True)
        with open(self.input_conf, "w") as fh:
            fh.write(data.input_conf(TV))
        failures = 0
        while not self._stop.is_set():
            entries = self.listing.value
            if not entries:
                self._stop.wait(2)
                continue
            e = data.pick(entries, self.recent)
            self.recent = (self.recent + [e.id])[-10:]
            self.now_playing, self.dirty = e, True
            try:
                proc = self._launch(e)
                if proc is None:
                    break
                code = proc.wait()
            except Exception as ex:
                code, self.problem = -1, f"mpv couldn't start: {ex}"
            self.proc = None
            if self._stop.is_set():
                break
            failures = 0 if code == 0 else failures + 1
            if failures:
                self.problem, self.dirty = f"Couldn't play “{data.clean_title(e.title)}”. Trying another.", True
                print(f"[{self.name}] mpv exited {code} on {e.url}", file=sys.stderr)
                self._stop.wait(min(60, 5 * failures))
            else:
                self.problem = None

    def _launch(self, e):
        """Start mpv for entry e, unless the channel is already stopping (checked under the same lock)."""
        chan = self.ctx.registry.number(self.name) if self.ctx.registry else 0
        with self._lock:
            if self._stop.is_set():
                return None
            self.proc = subprocess.Popen(data.mpv_args(e, chan or 0, self.title, ytdlp_path() or "yt-dlp",
                                                       self.input_conf),
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            try:                                # if memory runs out, the kernel kills mpv, not the host
                with open(oom_adj_path(self.proc.pid), "w") as fh:
                    fh.write("1000")
            except OSError:
                pass
            return self.proc

    @property
    def external(self):
        p = self.proc
        return p is not None and p.poll() is None

    def stop(self):
        self._stop.set()
        with self._lock:                       # a launch in progress finishes assigning proc first
            p = self.proc
        if p is not None and p.poll() is None:
            try:
                os.killpg(p.pid, 15)            # mpv and its yt-dlp helper
            except Exception:
                p.terminate()
            try:
                p.wait(3)
            except Exception:
                try:
                    os.killpg(p.pid, 9)
                except Exception:
                    p.kill()
        super().stop()

    @property
    def ready(self):
        return True

    # -- the card under the player (and when it can't play) -------------------------
    def draw_static(self, surf):
        text.draw(surf, self.blurb, (X0, 40), "sans-500", 24, theme.BONE, max_w=1060)
        if self.problem:
            text.draw(surf, "Can't play right now", (X0 - 4, 250), "display", 110, theme.CORAL)
            for i, line in enumerate(text.wrap(self.problem, "sans", 24, 1060)):
                text.draw(surf, line, (X0, 390 + i * 34), "sans", 24, theme.LICHEN)
            return
        if self.listing.value is None:
            msg = ("YouTube isn't answering." if self.listing.status == "offline" else
                   "Listing videos with yt-dlp. On a Pi Zero the first visit takes a minute or two; after that "
                   "the list is cached for six hours.")
            text.draw(surf, "Tuning in", (X0 - 4, 250), "display", 110, self.key)
            for i, line in enumerate(text.wrap(msg, "sans", 24, 1060)):
                text.draw(surf, line, (X0, 390 + i * 34), "sans", 24, theme.LICHEN)
            return
        e = self.now_playing
        text.draw(surf, "Now playing" if e else "Tuning in", (X0, 230), "sans", 24, theme.LICHEN)
        if e:
            lines = text.wrap(data.clean_title(e.title), "display", 84, 1060)[:3]
            for i, line in enumerate(lines):
                text.draw(surf, line, (X0 - 4, 262 + i * 88), "display", 84, self.key)
        text.draw(surf, f"{len(self.listing.value)} videos in rotation", (X0, 640), "sans", 18, theme.LICHEN)


def channel(name, title, urls, blurb, key, order, aliases=()):
    return type(f"Video_{name}", (VideoChannel,), dict(name=name, title=title, urls=tuple(urls), blurb=blurb,
                                                        key=key, order=order, aliases=tuple(aliases)))


def _from_config():
    cfg = config_mod.load()
    out = []
    for i, v in enumerate(cfg.raw.get("video") or []):
        try:
            out.append(channel(v["name"], v.get("title", v["name"].upper()), [v["url"]],
                               v.get("blurb", f"Videos from {v.get('title', v['name'])}"), theme.SEAGLASS, 105 + i))
        except KeyError:
            continue
    shorts = cfg.raw.get("shorts", {}).get("channels") if isinstance(cfg.raw.get("shorts"), dict) else None
    return out, shorts or DEFAULT_SHORTS


_extra, _shorts = _from_config()
MODULES = [
    channel("computerphile", "COMPUTERPHILE", ["https://www.youtube.com/@Computerphile/videos"],
            "Computer science explained, from Computerphile", (255, 196, 92), 100, aliases=("cphile",)),
    channel("shorts", "SHORTS", [f"https://www.youtube.com/{c}/shorts" for c in _shorts],
            "Short science and engineering videos", (255, 92, 160), 101),
    *_extra,
]
