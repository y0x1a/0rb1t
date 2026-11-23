"""Duck-typed stand-in for orb1t.app.App, enough for ReplTUI."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Resp:
    text: str = ""
    session_id: str | None = None


@dataclass
class Result:
    ok: bool = True
    message: str = ""
    clear: bool = False
    exit: bool = False
    new_session: bool = False
    session_id: str | None = None
    data: dict = field(default_factory=dict)


class _Engine:
    def ensure_available(self):
        pass


class FakeApp:
    def __init__(self, cwd=None, reply="echo", gate: threading.Event | None = None):
        self.cwd = Path(cwd or ".").resolve()
        self.config = {"ui": {"theme": "purple", "name": "0rb1t", "alt_screen": True, "show_banner": True},
                       "engine": {"name": "opencode"}}
        self.engine = _Engine()
        self.reply = reply
        self.gate = gate
        self.sent: list[tuple[str, str | None]] = []
        self.commands: list[str] = []
        self.shutdowns = 0

    def update_discord_presence(self):
        return {"enabled": False}

    def shutdown_integrations(self):
        self.shutdowns += 1

    def dispatch_command(self, text, *, session_id=None):
        self.commands.append(text)
        name = text.strip()[1:].split()[0] if text.strip()[1:] else ""
        if name == "exit":
            return Result(exit=True, message="disconnecting.")
        if name == "clear":
            return Result(clear=True)
        if name == "new":
            return Result(new_session=True, message="new session started.")
        if name == "version":
            return Result(message="0rb1t vTEST")
        return Result(ok=False, message=f"unknown command: /{name}")

    def send(self, message, *, session_id=None):
        self.sent.append((message, session_id))
        if self.gate is not None:
            self.gate.wait(5)
        if message.startswith("boom"):
            raise RuntimeError("engine exploded")
        return Resp(text=self.reply if self.reply != "echo" else f"echo: {message}", session_id="sess-0123456789")

    def __call__(self, cwd=None):  # lets a FakeApp instance stand in for the App class
        return self


class FakeTerm:
    is_tty = True

    def __init__(self, cols=80, rows=24):
        self.cols, self.rows = cols, rows
        self.out: list[str] = []
        self.cleaned = 0

    def size(self):
        return self.cols, self.rows

    def write(self, s):
        self.out.append(s)

    def flush(self):
        pass

    def cleanup(self):
        self.cleaned += 1

    def take(self) -> str:
        s = "".join(self.out)
        self.out.clear()
        return s
