"""Input buffer and key parsing for 0rb1t TUI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class KeyEvent:
    kind: str
    value: str = ""


class InputBuffer:
    """Editable multiline buffer with cursor. Prompt is not part of buffer."""

    def __init__(self) -> None:
        self.lines: list[str] = [""]
        self.row = 0
        self.col = 0

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def clear(self) -> None:
        self.lines = [""]
        self.row = 0
        self.col = 0

    def set_text(self, text: str) -> None:
        self.lines = text.split("\n") if text else [""]
        self.row = len(self.lines) - 1
        self.col = len(self.lines[self.row])

    def insert(self, s: str) -> None:
        if not s:
            return
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        for ch in s:
            if ch == "\n":
                self.newline()
            elif ch == "\t":
                self._insert_str("    ")
            elif ord(ch) >= 32 or ch == "\u001b":
                # Escape chars should not be inserted; caller should sanitize.
                if ch != "\u001b":
                    self._insert_str(ch)
            else:
                pass

    def _insert_str(self, s: str) -> None:
        line = self.lines[self.row]
        self.lines[self.row] = line[: self.col] + s + line[self.col :]
        self.col += len(s)

    def newline(self) -> None:
        line = self.lines[self.row]
        left, right = line[: self.col], line[self.col :]
        self.lines[self.row] = left
        self.lines.insert(self.row + 1, right)
        self.row += 1
        self.col = 0

    def backspace(self) -> None:
        if self.col > 0:
            line = self.lines[self.row]
            self.lines[self.row] = line[: self.col - 1] + line[self.col :]
            self.col -= 1
            return
        if self.row > 0:
            prev = self.lines[self.row - 1]
            cur = self.lines.pop(self.row)
            self.row -= 1
            self.col = len(prev)
            self.lines[self.row] = prev + cur

    def delete(self) -> None:
        line = self.lines[self.row]
        if self.col < len(line):
            self.lines[self.row] = line[: self.col] + line[self.col + 1 :]
            return
        if self.row < len(self.lines) - 1:
            nxt = self.lines.pop(self.row + 1)
            self.lines[self.row] = line + nxt

    def left(self) -> None:
        if self.col > 0:
            self.col -= 1
        elif self.row > 0:
            self.row -= 1
            self.col = len(self.lines[self.row])

    def right(self) -> None:
        line = self.lines[self.row]
        if self.col < len(line):
            self.col += 1
        elif self.row < len(self.lines) - 1:
            self.row += 1
            self.col = 0

    def up(self) -> None:
        if self.row == 0:
            self.col = 0
            return
        self.row -= 1
        self.col = min(self.col, len(self.lines[self.row]))

    def down(self) -> None:
        if self.row >= len(self.lines) - 1:
            self.col = len(self.lines[self.row])
            return
        self.row += 1
        self.col = min(self.col, len(self.lines[self.row]))

    def home(self) -> None:
        self.col = 0

    def end(self) -> None:
        self.col = len(self.lines[self.row])

    def ctrl_a(self) -> None:
        self.home()

    def ctrl_e(self) -> None:
        self.end()

    def kill_to_end(self) -> None:
        self.lines[self.row] = self.lines[self.row][: self.col]

    def kill_to_start(self) -> None:
        self.lines[self.row] = self.lines[self.row][self.col :]
        self.col = 0


class KeyParser:
    """Parse terminal bytes into key events, preserving unknown sequences as ignored."""

    def __init__(self) -> None:
        self.buf = b""

    def feed(self, data: bytes) -> list[KeyEvent]:
        self.buf += data
        events: list[KeyEvent] = []
        while self.buf:
            ev, consumed = self._next()
            if consumed == 0:
                break
            self.buf = self.buf[consumed:]
            if ev is not None:
                events.append(ev)
        # Avoid unbounded growth on garbage
        if len(self.buf) > 4096:
            self.buf = b""
        return events

    def _next(self) -> tuple[KeyEvent | None, int]:
        b = self.buf
        if not b:
            return None, 0
        # Enter
        if b[0] in (10, 13):
            # CRLF
            if b.startswith(b"\r\n"):
                return KeyEvent("enter"), 2
            return KeyEvent("enter"), 1
        if b[0] == 9:
            return KeyEvent("tab"), 1
        if b[0] == 127 or b[0] == 8:
            return KeyEvent("backspace"), 1
        if b[0] == 3:
            return KeyEvent("ctrl_c"), 1
        if b[0] == 4:
            return KeyEvent("ctrl_d"), 1
        if b[0] == 1:
            return KeyEvent("ctrl_a"), 1
        if b[0] == 5:
            return KeyEvent("ctrl_e"), 1
        if b[0] == 11:
            return KeyEvent("ctrl_k"), 1
        if b[0] == 21:
            return KeyEvent("ctrl_u"), 1
        if b[0] == 12:
            return KeyEvent("ctrl_l"), 1
        if b[0] == 0x1B:
            return self._parse_escape(b)
        if b[0] < 32:
            return None, 1
        # UTF-8 text
        try:
            ch = b[:1].decode("utf-8")
            return KeyEvent("char", ch), 1
        except UnicodeDecodeError:
            for n in range(2, 5):
                if len(b) < n:
                    return None, 0
                try:
                    ch = b[:n].decode("utf-8")
                    return KeyEvent("char", ch), n
                except UnicodeDecodeError:
                    continue
            return None, 1

    def _parse_escape(self, b: bytes) -> tuple[KeyEvent | None, int]:
        if len(b) == 1:
            # Bare ESC; wait briefly? Caller feeds with timeout; treat as esc.
            return KeyEvent("esc"), 1
        if b[1:2] == b"[":
            return self._parse_csi(b)
        if b[1:2] == b"O":
            if len(b) < 3:
                return None, 0
            c = chr(b[2])
            mapping = {"A": "up", "B": "down", "C": "right", "D": "left", "H": "home", "F": "end"}
            if c in mapping:
                return KeyEvent(mapping[c]), 3
            return None, 3
        # Alt+Enter common encoding
        if b[1] in (10, 13):
            if b.startswith(b"\x1b\r\n"):
                return KeyEvent("shift_enter"), 3
            return KeyEvent("shift_enter"), 2
        # Alt+key: ignore for now except maybe backspace; consume 2
        return None, 2

    def _parse_csi(self, b: bytes) -> tuple[KeyEvent | None, int]:
        # Find final byte 0x40..0x7E
        i = 2
        while i < len(b):
            c = b[i]
            if 0x40 <= c <= 0x7E:
                final = chr(c)
                params = b[2:i]
                seq = b[: i + 1]
                return self._csi_event(params, final), i + 1
            i += 1
            if i > 64:
                return None, i
        return None, 0

    def _csi_event(self, params: bytes, final: str) -> KeyEvent | None:
        ptxt = params.decode("ascii", errors="ignore")
        # SGR mouse: <btn;x;yM/m
        if final in "Mm" and ptxt.startswith("<"):
            return self._mouse_event(ptxt[1:], final)
        if final == "A":
            return KeyEvent("up")
        if final == "B":
            return KeyEvent("down")
        if final == "C":
            return KeyEvent("right")
        if final == "D":
            return KeyEvent("left")
        if final in ("H",):
            return KeyEvent("home")
        if final in ("F",):
            return KeyEvent("end")
        if final == "~":
            num = ptxt.split(";")[0]
            if num == "3":
                return KeyEvent("delete")
            if num == "1" or num == "7":
                return KeyEvent("home")
            if num == "4" or num == "8":
                return KeyEvent("end")
            if num == "5":
                return KeyEvent("page_up")
            if num == "6":
                return KeyEvent("page_down")
            if num == "13":
                mod = ptxt.split(";")[1] if ";" in ptxt else ""
                if mod == "2":
                    return KeyEvent("shift_enter")
                return KeyEvent("enter")
            if num == "27":
                # xterm modifyOtherKeys: CSI 27;mod;key~
                parts = ptxt.split(";")
                if len(parts) >= 3 and parts[1] == "2" and parts[2] == "13":
                    return KeyEvent("shift_enter")
                return None
            if num == "200":
                return KeyEvent("paste_start")
            if num == "201":
                return KeyEvent("paste_end")
            return None
        # Shift+Enter in kitty/xterm modifyOtherKeys / CSI u forms
        if final == "u":
            # CSI 13;2u
            parts = ptxt.split(";")
            if parts and parts[0] == "13" and len(parts) > 1 and parts[1].startswith("2"):
                return KeyEvent("shift_enter")
            if parts and parts[0] == "13":
                return KeyEvent("enter")
            return None
        # Focus/mouse other modes ignored
        return None

    def _mouse_event(self, params: str, final: str) -> KeyEvent | None:
        # btn;x;y
        try:
            parts = params.split(";")
            btn = int(parts[0])
            # Wheel: 64 up, 65 down in SGR button encoding
            if btn & 64:
                wheel = btn & 0x41  # 64 or 65
                if (btn & 1) == 0:
                    return KeyEvent("scroll_up")
                return KeyEvent("scroll_down")
        except Exception:
            return None
        return KeyEvent("mouse")
