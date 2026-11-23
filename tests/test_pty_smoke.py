"""End-to-end: run the real TUI in a pseudo-terminal and drive it with keystrokes."""
import os
import select
import sys
import time

try:
    import pytest
except Exception:
    import types; pytest=types.SimpleNamespace(skip=lambda *a,**k: (_ for _ in ()).throw(Exception("skip")), mark=types.SimpleNamespace(parametrize=lambda *a,**k: (lambda f:f)))

pty = pytest.importorskip("pty")
fcntl = pytest.importorskip("fcntl")
termios = pytest.importorskip("termios")
import signal
import struct

HERE = os.path.dirname(__file__)
SRC = os.path.join(HERE, "..", "src")
BOOT = (
    "import orb1t.cli as c; from _fakeapp import FakeApp; c.App = FakeApp; "
    "raise SystemExit(c.main([]))"
)


class Session:
    def __init__(self, cols=100, rows=30):
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            env = dict(os.environ, PYTHONPATH=os.pathsep.join([SRC, HERE]), TERM="xterm-256color", COLORTERM="truecolor")
            os.execvpe(sys.executable, [sys.executable, "-c", BOOT], env)
        self.size(cols, rows)
        self.buf = b""
        self.status = None

    def size(self, cols, rows):
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    def read_until(self, needle: bytes, timeout=5.0) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if needle in self.buf:
                return True
            r, _, _ = select.select([self.fd], [], [], 0.1)
            if r:
                try:
                    d = os.read(self.fd, 65536)
                except OSError:
                    break
                if not d:
                    break
                self.buf += d
        return needle in self.buf

    def send(self, data: bytes):
        os.write(self.fd, data)

    def wait_exit(self, timeout=5.0):
        end = time.time() + timeout
        while time.time() < end:
            self.read_until(b"\0never", 0.1)
            pid, st = os.waitpid(self.pid, os.WNOHANG)
            if pid:
                self.status = os.WEXITSTATUS(st) if os.WIFEXITED(st) else -os.WTERMSIG(st)
                return self.status
        os.kill(self.pid, signal.SIGKILL)
        os.waitpid(self.pid, 0)
        return None


@pytest.fixture
def session():
    s = Session()
    yield s
    try:
        os.kill(s.pid, signal.SIGKILL)
        os.waitpid(s.pid, 0)
    except Exception:
        pass


def test_full_session_and_clean_exit(session):
    assert session.read_until("terminal intelligence environment".encode())      # startup/empty state
    assert b"\x1b[?1049h" in session.buf                                        # alt screen
    assert b"\x1b[?1000h" in session.buf and b"\x1b[?2004h" in session.buf      # mouse + paste
    session.send(b"/version\r")
    assert session.read_until(b"0rb1t vTEST")                                   # command dispatch
    session.send(b"\x1b[<64;10;5M")                                             # wheel up: must not crash
    session.send(b"hello world\r")
    assert session.read_until(b"echo: hello world")                             # engine roundtrip
    session.send(b"x\x1b[13;2uy")                                               # shift+enter newline
    assert session.read_until(b"\x1b[?2026l")
    session.send(b"\x15\x7f\x15")                                              # clear both lines
    session.size(70, 20)
    os.kill(session.pid, signal.SIGWINCH)
    session.send(b"\x0c")                                                       # ctrl+l repaint
    assert session.read_until(b"\x1b[2J", 3)                                  # resize clears once
    session.send(b"/exit\r")
    assert session.wait_exit() == 0
    tail = session.buf
    assert tail.rfind(b"\x1b[?1049l") > tail.rfind(b"\x1b[?1049h")            # left alt screen
    assert b"\x1b[0 q" in tail                                                 # cursor shape restored
    assert b"\x1b[?25h" in tail and b"\x1b[?1000l" in tail                      # cursor shown, mouse off
    assert tail.rfind(b"\x1b[?25l") < tail.rfind(b"\x1b[?25h")


def test_sigterm_still_cleans_up(session):
    assert session.read_until(b"type a message")
    os.kill(session.pid, signal.SIGTERM)
    assert session.wait_exit() == 0
    assert b"\x1b[?1049l" in session.buf and b"\x1b[?1000l" in session.buf
