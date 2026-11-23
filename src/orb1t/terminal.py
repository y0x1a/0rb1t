"""Low-level terminal control for 0rb1t TUI."""

from __future__ import annotations

import os
import shutil
import signal
import sys
from typing import Callable

try:
    import termios
    import tty
except Exception:  # pragma: no cover - non-posix
    termios = None  # type: ignore[assignment]
    tty = None  # type: ignore[assignment]


class Terminal:
    """Terminal mode manager with safe cleanup."""

    def __init__(self) -> None:
        self.fd: int | None = sys.stdin.fileno() if sys.stdin.isatty() else None
        self._orig_attrs = None
        self._alt = False
        self._raw = False
        self._mouse = False
        self._callbacks: list[Callable[[], None]] = []

    @property
    def is_tty(self) -> bool:
        return bool(
            sys.stdin.isatty()
            and sys.stdout.isatty()
            and self.fd is not None
            and termios is not None
        )

    def size(self) -> tuple[int, int]:
        try:
            s = os.get_terminal_size(self.fd if self.fd is not None else sys.stdout.fileno())
        except Exception:
            s = shutil.get_terminal_size((100, 30))
        cols = max(20, int(s.columns))
        rows = max(8, int(s.lines))
        return cols, rows

    def write(self, s: str) -> None:
        try:
            sys.stdout.write(s)
        except Exception:
            pass

    def flush(self) -> None:
        try:
            sys.stdout.flush()
        except Exception:
            pass

    def enter_alt(self) -> None:
        if not sys.stdout.isatty() or self._alt:
            return
        # Alt screen, home, clear, hide cursor during draws; we'll show in input.
        self.write("\033[?1049h\033[H\033[2J")
        self.flush()
        self._alt = True

    def leave_alt(self) -> None:
        if not sys.stdout.isatty() or not self._alt:
            self._alt = False
            return
        self.write("\033[?1049l")
        self.flush()
        self._alt = False

    def enable_mouse(self) -> None:
        if not sys.stdout.isatty() or self._mouse:
            return
        # SGR mouse + button events + wheel. Focus reporting off by default.
        self.write("\033[?1000h\033[?1006h\033[?1015l\033[?1002l\033[?1003l")
        self.flush()
        self._mouse = True

    def disable_mouse(self) -> None:
        if not sys.stdout.isatty():
            self._mouse = False
            return
        self.write("\033[?1000l\033[?1002l\033[?1003l\033[?1005l\033[?1006l\033[?1015l\033[?1004l")
        self.flush()
        self._mouse = False

    def enable_raw(self) -> None:
        if not self.is_tty or self._raw:
            return
        assert termios is not None and self.fd is not None
        self._orig_attrs = termios.tcgetattr(self.fd)
        # Raw-ish but keep output processing; we want Ctrl+C as byte.
        attrs = termios.tcgetattr(self.fd)
        attrs[0] &= ~(termios.IXON | termios.ICRNL | termios.BRKINT | termios.INPCK | termios.ISTRIP)
        # Keep OPOST so \n maps to \r\n in output; renderer also uses \r\n.
        attrs[1] |= termios.OPOST
        attrs[2] |= termios.CS8
        attrs[3] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 1
        termios.tcsetattr(self.fd, termios.TCSADRAIN, attrs)
        self._raw = True

    def disable_raw(self) -> None:
        if not self.is_tty or not self._raw or self._orig_attrs is None:
            self._raw = False
            return
        assert termios is not None and self.fd is not None
        try:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self._orig_attrs)
        except Exception:
            pass
        self._raw = False

    def cleanup(self) -> None:
        for cb in list(self._callbacks):
            try:
                cb()
            except Exception:
                pass
        try:
            self.disable_mouse()
        except Exception:
            pass
        try:
            self.disable_raw()
        except Exception:
            pass
        try:
            self.show_cursor()
        except Exception:
            pass
        try:
            self.leave_alt()
        except Exception:
            pass
        try:
            self.write("\033[0m\033[0 q\033[?2026l\033[?2004l\033[?1004l")  # reset SGR, cursor shape, sync, paste, focus
            self.flush()
        except Exception:
            pass

    def on_cleanup(self, cb: Callable[[], None]) -> None:
        self._callbacks.append(cb)

    def show_cursor(self) -> None:
        self.write("\033[?25h")
        self.flush()

    def hide_cursor(self) -> None:
        self.write("\033[?25l")
        self.flush()

    def move(self, row: int, col: int) -> str:
        return f"\033[{max(1,row)};{max(1,col)}H"

    def clear_line(self) -> str:
        return "\033[2K"
