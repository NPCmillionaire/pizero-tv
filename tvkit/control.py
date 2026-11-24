"""Line-based unix-socket control channel between `tv` and the host."""
import os, socket


class NotRunning(Exception):
    pass


class Server:
    def __init__(self, path):
        self.path = path
        if os.path.exists(path):
            os.unlink(path)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(path)
        self.sock.listen(4)
        self.sock.setblocking(False)

    def poll(self, handler):
        """Serve any pending connections (non-blocking). handler(line) -> reply str."""
        while True:
            try:
                conn, _ = self.sock.accept()
            except (BlockingIOError, InterruptedError):
                return
            with conn:
                conn.settimeout(2)
                try:
                    line = conn.makefile("r").readline().strip()
                    reply = handler(line)
                except Exception as e:
                    reply = f"error: {e}"
                try:
                    conn.sendall((reply + "\n").encode())
                except OSError:
                    pass

    def close(self):
        self.sock.close()
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass


def default_path():
    return os.path.join(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"), "pizero-tv.sock")


def send(path, line, timeout=10):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(path)
    except (FileNotFoundError, ConnectionRefusedError) as e:
        raise NotRunning(str(e)) from e
    with s:
        s.sendall((line.strip() + "\n").encode())
        return s.makefile("r").read().strip()
