"""`tv` — control the pizero-tv display, here or on another Pi (-H host)."""
import json, os, shlex, subprocess, sys

from . import control

HELP = """usage: tv [-H HOST] <command>

  tv                     what's on screen
  tv <module>            tune to a channel by name (see tv list)
  tv <number>            tune to a channel by number (tv 0 is the guide)
  tv up | tv down        flip channels
  tv next                skip to the next channel in the rotation
  tv cycle [SEC] [M...]  rotate through modules (default: all, every 90 s)
  tv stop                standby screen
  tv list                installed modules
  tv screenshot [PATH]   save what the TV shows (PNG)
  tv logs                follow the display host's log
  tv start               start the display host if it isn't running

  -H HOST                run the command on another Pi over ssh (e.g. tv -H pizero weather)
"""
REMOTE_TV = "~/pizero-tv/bin/tv"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.expanduser("~/.local/state/pizero-tv/tvd.log")


class Usage(Exception):
    pass


def to_command(args, reg):
    if not args or args[0] == "status":
        return "status"
    cmd, rest = args[0], args[1:]
    if cmd in ("next", "stop", "reload", "up", "down"):
        return cmd
    if cmd.isdigit():
        return f"ch {int(cmd)}"
    if cmd == "digit" and rest and rest[0].isdigit():
        return f"digit {rest[0]}"
    if cmd == "ch" and rest and rest[0].isdigit():
        return f"ch {int(rest[0])}"
    if cmd == "cycle":
        return " ".join(["cycle", *[_module(a, reg) if not a.isdigit() else a for a in rest]])
    if cmd == "show":
        if not rest:
            raise Usage("tv show needs a module name. " + _choices(reg))
        return f"show {_module(rest[0], reg)}"
    if cmd == "screenshot":
        return f"screenshot {os.path.abspath(rest[0]) if rest else '/tmp/tv-screenshot.png'}"
    return f"show {_module(cmd, reg)}"


def _module(name, reg):
    cls = reg.get(name)
    if cls is None:
        raise Usage(f"No module called {name!r}. {_choices(reg)}")
    return cls.name


def _choices(reg):
    return "Modules: " + ", ".join(reg.names())


def remote_argv(host, args):
    return ["ssh", "-o", "ConnectTimeout=10", host, REMOTE_TV, *[shlex.quote(a) for a in args]]


def _pretty(status):
    s = json.loads(status)
    if s["phase"] == "standby":
        return "Standby (nothing on screen)."
    what = {"static": "tuning in", "crash": "crashed, moving on"}.get(s["phase"], "on screen")
    ch = f"channel {s['channel']:02d}, " if s.get("channel") is not None else ""
    line = f"{ch}{s['module']} — {what} for {int(s['since_s'])} s"
    if s["mode"] == "cycle":
        names = s["cycle_names"] or ["all modules"]
        line += f"; cycling every {s['cycle_seconds']} s through {', '.join(names)}"
    if s.get("data"):
        line += f"; data {s['data']}"
    return line


def _start():
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    env.setdefault("WAYLAND_DISPLAY", "wayland-0")
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "ab") as log:
        subprocess.Popen([sys.executable, "-m", "tvkit"], cwd=ROOT, env=env, stdout=log, stderr=log,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    print("Display host starting; the TV tunes in within a few seconds.")
    return 0


def main(argv=None, reg=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] in (["-h"], ["--help"], ["help"]):
        print(HELP)
        return 0
    if args[:1] == ["-H"]:
        if len(args) < 2:
            print(HELP, file=sys.stderr)
            return 1
        host, rest = args[1], args[2:]
        if rest[:1] == ["screenshot"]:
            local = os.path.abspath(rest[1]) if len(rest) > 1 else os.path.abspath("tv-screenshot.png")
            r = subprocess.call(remote_argv(host, ["screenshot", "/tmp/tv-screenshot.png"]))
            if r == 0:
                r = subprocess.call(["scp", "-q", f"{host}:/tmp/tv-screenshot.png", local])
            if r == 0:
                print(f"Saved {local}")
            return r
        return subprocess.call(remote_argv(host, rest))
    if args[:1] == ["logs"]:
        return subprocess.call(["tail", "-n", "60", "-f", LOG])
    if args[:1] == ["start"]:
        try:
            control.send(control.default_path(), "status")
            print("The display host is already running.")
            return 0
        except control.NotRunning:
            return _start()
    if reg is None:
        sys.path.insert(0, ROOT)
        from . import registry
        reg = registry.discover()
    if args[:1] == ["list"]:
        for i, c in enumerate(reg.channels()):
            alias = f"  (also: {', '.join(c.aliases)})" if c.aliases else ""
            print(f"{i:02d}  {c.name:<14} {c.blurb}{alias}")
        return 0
    try:
        line = to_command(args, reg)
    except Usage as e:
        print(e, file=sys.stderr)
        return 1
    try:
        reply = control.send(control.default_path(), line)
    except control.NotRunning:
        print("tvd isn't running. Start it with: tv start", file=sys.stderr)
        return 2
    if reply.startswith("error"):
        print(reply, file=sys.stderr)
        return 1
    if line == "status":
        print(_pretty(reply))
    elif line.startswith("screenshot"):
        print(f"Saved {line.split(' ', 1)[1]}")
    return 0
