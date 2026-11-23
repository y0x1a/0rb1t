"""Terminal input and mode helpers."""

from __future__ import annotations

import atexit
import os
import readline  # noqa: F401 - enables line editing/history for input() on Linux
import signal
import sys
from pathlib import Path

# Mouse reporting/focus/bracketed-paste modes sometimes enabled by programs/terminals.
# Disable them defensively to prevent raw escape sequences leaking into input.
_DISABLE_MOUSE = (
    "\033[?1000l"  # X10 mouse
    "\033[?1002l"  # button-event tracking
    "\033[?1003l"  # any-event tracking
    "\033[?1005l"  # utf-8 mouse encoding
    "\033[?1006l"  # SGR mouse encoding
    "\033[?1015l"  # urxvt mouse encoding
    "\033[?1004l"  # focus reporting
    "\033[?2004l"  # bracketed paste
)

_RESET_MODES = (
    "\033[?25h"  # show cursor
    "\033[?1049l"  # leave alt screen
    "\033[0m"  # reset attrs
)

_alt_screen_active = False
_cleaned_up = False


def _write(seq: str) -> None:
    try:
        if sys.stdout.isatty():
            sys.stdout.write(seq)
            sys.stdout.flush()
    except Exception:
        pass


def disable_mouse_reporting() -> None:
    _write(_DISABLE_MOUSE)


def enter_alt_screen() -> None:
    global _alt_screen_active
    if not sys.stdout.isatty():
        return
    # Enter alt screen, clear, home, show cursor, disable mouse reporting.
    _write("\033[?1049h\033[?25h\033[2J\033[H" + _DISABLE_MOUSE)
    _alt_screen_active = True


def leave_alt_screen() -> None:
    global _alt_screen_active
    if not sys.stdout.isatty():
        return
    _write(_DISABLE_MOUSE + _RESET_MODES)
    _alt_screen_active = False


def cleanup() -> None:
    global _cleaned_up
    if _cleaned_up:
        return
    _cleaned_up = True
    disable_mouse_reporting()
    if _alt_screen_active or sys.stdout.isatty():
        _write(_RESET_MODES)
    try:
        sys.stdout.flush()
    except Exception:
        pass


def install_signal_handlers(previous_sigint=None) -> None:
    """Install handlers that restore terminal state on exit signals."""

    def _handler(signum, frame):
        cleanup()
        # Re-raise default behavior
        signal.signal(signum, signal.SIG_DFL)
        try:
            os.kill(os.getpid(), signum)
        except Exception:
            raise SystemExit(128 + signum)

    for sig in (signal.SIGTERM, signal.SIGHUP):
        try:
            signal.signal(sig, _handler)
        except Exception:
            pass

    # SIGINT: keep KeyboardInterrupt behavior but cleanup if it escapes badly;
    # main loop handles KeyboardInterrupt.
    if previous_sigint is not None:
        try:
            signal.signal(signal.SIGINT, previous_sigint)
        except Exception:
            pass


def init_readline(history_path: Path | None = None) -> None:
    """Configure readline for line editing and history."""
    try:
        import readline  # type: ignore

        readline.parse_and_bind("tab: complete")
        # Ensure arrow keys work in common terminals; readline usually handles this,
        # but explicit bindings help when inputrc is minimal.
        readline.parse_and_bind(r'"\e[A": previous-history')
        readline.parse_and_bind(r'"\e[B": next-history')
        readline.parse_and_bind(r'"\e[C": forward-char')
        readline.parse_and_bind(r'"\e[D": backward-char')
        if history_path is not None:
            try:
                history_path.parent.mkdir(parents=True, exist_ok=True)
                if history_path.exists():
                    readline.read_history_file(str(history_path))
                readline.set_history_length(500)
            except Exception:
                pass
        # Store path on module for save
        global _history_path
        _history_path = history_path
    except Exception:
        pass


_history_path: Path | None = None


def save_readline_history() -> None:
    try:
        import readline  # type: ignore

        if _history_path is not None:
            _history_path.parent.mkdir(parents=True, exist_ok=True)
            readline.write_history_file(str(_history_path))
    except Exception:
        pass


def read_input(prompt_display: str, prompt_input: str) -> str:
    """Read a line of input.

    prompt_display is printed before input (may be multiline/ANSI).
    prompt_input is the actual prompt passed to input() for readline correctness.
    """
    if prompt_display:
        print(prompt_display, end="")
        sys.stdout.flush()
    try:
        line = input(prompt_input)
    except EOFError:
        raise
    except KeyboardInterrupt:
        raise
    # Defensive: strip stray mouse/CSI sequences that may leak into input.
    cleaned = _strip_control_sequences(line)
    return cleaned


def _strip_control_sequences(text: str) -> str:
    """Remove stray terminal escape sequences from input.

    Keeps normal text, tabs, and unicode. Removes CSI/OSC-like control sequences
    that can appear when mouse reporting or malformed terminal modes leak.
    """
    if "\x1b" not in text and "\x9b" not in text:
        return text
    import re

    # CSI: ESC [ ... final byte @-~
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    # OSC: ESC ] ... BEL or ST
    text = re.sub(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)", "", text)
    # SS3: ESC O X
    text = re.sub(r"\x1bO.", "", text)
    # Lone ESC
    text = text.replace("\x1b", "")
    # CSI C1
    text = re.sub(r"\x9b[0-?]*[ -/]*[@-~]", "", text)
    return text
