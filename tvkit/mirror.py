"""Terminal mirroring: `tv mirror` streams a shell's output to the host, which keeps a terminal screen.

Wire format, one frame at a time: 1 type byte, 4-byte big-endian length, payload.
  H  hello, JSON {"host", "cols", "rows"}        S  resize, JSON {"cols", "rows"}
  D  terminal output bytes (UTF-8, escape sequences and all)
Nothing is written to disk; the screen lives in the host's memory until the mirror disconnects.
"""
import json, os, socket, struct, time

MAX_FRAME = 1 << 20
MAX_COLS, MAX_ROWS = 160, 50


def frame(kind, payload):
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload).encode()
    return kind.encode() + struct.pack(">I", len(payload)) + payload


class Decoder:
    """Feed bytes in any chunking; get whole (kind, payload) frames out."""

    def __init__(self):
        self.buf = b""

    def feed(self, data):
        self.buf += data
        out = []
        while len(self.buf) >= 5:
            kind, n = chr(self.buf[0]), struct.unpack(">I", self.buf[1:5])[0]
            if n > MAX_FRAME or kind not in "HSD":
                raise ValueError("bad mirror frame")
            if len(self.buf) < 5 + n:
                break
            out.append((kind, self.buf[5:5 + n]))
            self.buf = self.buf[5 + n:]
        return out


def default_path():
    return os.path.join(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"), "pizero-tv-mirror.sock")


def _size(d):
    return max(20, min(MAX_COLS, int(d.get("cols") or 80))), max(5, min(MAX_ROWS, int(d.get("rows") or 24)))


class Session:
    """One connected mirror: a pyte screen fed by its frames."""

    def __init__(self):
        import pyte
        self.pyte = pyte
        self.host, self.cols, self.rows = "a terminal", 80, 24
        self.screen = pyte.Screen(self.cols, self.rows)
        self.stream = pyte.ByteStream(self.screen)
        self.started, self.last = time.time(), time.time()
        self.dec = Decoder()
        self.version = 0

    def feed(self, data):
        for kind, payload in self.dec.feed(data):
            if kind in "HS":
                d = json.loads(payload or b"{}")
                if kind == "H":
                    self.host = str(d.get("host") or self.host)[:40]
                self.cols, self.rows = _size(d)
                self.screen.resize(self.rows, self.cols)
            else:
                self.stream.feed(payload)
            self.last = time.time()
            self.version += 1


class Server:
    """Non-blocking listener the host polls each frame. Holds at most one mirror at a time."""

    def __init__(self, path=None):
        self.path = path or default_path()
        if os.path.exists(self.path):
            os.unlink(self.path)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(self.path)
        os.chmod(self.path, 0o600)                 # only this user can mirror onto the TV
        self.sock.listen(1)
        self.sock.setblocking(False)
        self.conn, self.session = None, None

    def poll(self):
        """Returns 'connected', 'disconnected' or None."""
        event = None
        if self.conn is None:
            try:
                self.conn, _ = self.sock.accept()
                self.conn.setblocking(False)
                self.session = Session()
                event = "connected"
            except (BlockingIOError, InterruptedError):
                return None
            except ImportError:
                self.conn.close()
                self.conn = None
                return None
        try:
            for _ in range(32):
                data = self.conn.recv(65536)
                if not data:
                    return self._drop()
                self.session.feed(data)
        except (BlockingIOError, InterruptedError):
            pass
        except (OSError, ValueError):
            return self._drop()
        return event

    def _drop(self):
        try:
            self.conn.close()
        except OSError:
            pass
        self.conn = None
        return "disconnected"

    def close(self):
        if self.conn:
            self._drop()
        self.sock.close()
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass


# -- the sending side (`tv mirror` on any machine) -------------------------------------
def run_mirror(send, host_label):
    """Run $SHELL in a pseudo-terminal; show it here as usual and send every byte to `send` (a writable file)."""
    import fcntl, pty, select, signal, sys, termios, tty

    def winsize():
        try:
            rows, cols = struct.unpack("hh", fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, b"\0" * 4))
            return {"cols": cols, "rows": rows}
        except OSError:
            return {"cols": 80, "rows": 24}

    pid, fd = pty.fork()
    if pid == 0:
        os.environ["PIZERO_TV_MIRROR"] = "1"
        shell = os.environ.get("SHELL", "/bin/sh")
        os.execvp(shell, [shell, "-l"])
    size = winsize()

    def apply(sz):
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("hhhh", sz["rows"], sz["cols"], 0, 0))

    apply(size)
    send.write(frame("H", dict(size, host=host_label)))
    send.flush()

    def on_winch(*_):
        sz = winsize()
        apply(sz)
        try:
            send.write(frame("S", sz))
            send.flush()
        except OSError:
            pass
    signal.signal(signal.SIGWINCH, on_winch)
    old = termios.tcgetattr(sys.stdin.fileno()) if sys.stdin.isatty() else None
    if old:
        tty.setraw(sys.stdin.fileno())
    try:
        while True:
            try:
                r, _, _ = select.select([fd, sys.stdin.fileno()], [], [])
            except InterruptedError:
                continue
            if fd in r:
                try:
                    data = os.read(fd, 65536)
                except OSError:
                    break
                if not data:
                    break
                os.write(sys.stdout.fileno(), data)
                try:
                    send.write(frame("D", data))
                    send.flush()
                except OSError:
                    pass                           # the TV went away; keep the shell working
            if sys.stdin.fileno() in r:
                data = os.read(sys.stdin.fileno(), 65536)
                if not data:
                    break
                os.write(fd, data)
    finally:
        if old:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old)
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass
    return 0
