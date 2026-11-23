"""Optional Discord Rich Presence integration for 0rb1t.

Uses Discord local IPC socket. Best-effort: failures never block app.
"""

from __future__ import annotations

import json
import os
import socket
import struct
import time
import uuid
from dataclasses import dataclass
from typing import Any


OP_HANDSHAKE = 0
OP_FRAME = 1

# Rotating presence lines. No filler AI adjectives — just plain verbs paired
# with the configured assistant name. One phrase per wall-clock minute.
ACTIVITY_PHRASES = (
    "Building with {name}",
    "Shipping with {name}",
    "Coding with {name}",
    "Debugging with {name}",
    "Refactoring with {name}",
    "Deep work with {name}",
)

REPO_URL = "github.com/y0x1a/0rb1t"


@dataclass
class DiscordConfig:
    enabled: bool = False
    client_id: str = ""
    large_image: str = "orb1t"
    large_text: str = "0rb1t"


class DiscordRPC:
    def __init__(self) -> None:
        self.sock: socket.socket | None = None
        self.client_id: str = ""
        self.connected: bool = False
        self.last_error: str = ""
        self.last_socket: str = ""
        self.last_update_ok: bool | None = None
        self.last_update_at: float | None = None

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None
        self.connected = False
        self.client_id = ""

    def _socket_paths(self) -> list[str]:
        bases = []
        for env in ("XDG_RUNTIME_DIR", "TMPDIR", "TMP", "TEMP"):
            v = os.environ.get(env)
            if v:
                bases.append(v)
        bases.append("/tmp")
        paths = []
        for base in bases:
            for i in range(0, 10):
                paths.append(os.path.join(base, f"discord-ipc-{i}"))
        seen = set()
        out = []
        for p in paths:
            if p not in seen:
                seen.add(p)
                out.append(p)
        return out

    def discover_socket(self) -> str | None:
        for path in self._socket_paths():
            try:
                if os.path.exists(path):
                    return path
            except Exception:
                continue
        return None

    def connect(self, client_id: str, timeout: float = 0.75) -> bool:
        if not client_id:
            self.last_error = "missing client_id"
            return False
        if self.connected and self.sock and self.client_id == client_id:
            return True
        self.close()
        payload = json.dumps({"v": 1, "client_id": str(client_id)}).encode("utf-8")
        header = struct.pack("<II", OP_HANDSHAKE, len(payload))
        last_err = "no discord ipc socket found"
        for path in self._socket_paths():
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(timeout)
                s.connect(path)
                s.sendall(header + payload)
                try:
                    self._recv(s, timeout=timeout)
                except Exception:
                    pass
                s.settimeout(timeout)
                self.sock = s
                self.client_id = str(client_id)
                self.connected = True
                self.last_error = ""
                self.last_socket = path
                return True
            except Exception as e:
                last_err = str(e)
                try:
                    s.close()
                except Exception:
                    pass
        self.close()
        self.last_error = last_err
        return False

    def _recv(self, sock: socket.socket, timeout: float = 0.75):
        sock.settimeout(timeout)
        head = self._recv_exact(sock, 8)
        op, n = struct.unpack("<II", head)
        data = self._recv_exact(sock, n) if n else b""
        return op, data

    def _recv_exact(self, sock: socket.socket, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                raise EOFError("socket closed")
            buf += chunk
        return buf

    def send_activity(self, activity: dict[str, Any] | None, timeout: float = 0.75) -> bool:
        if not self.connected or not self.sock:
            self.last_update_ok = False
            self.last_error = self.last_error or "not connected"
            return False
        payload = {
            "cmd": "SET_ACTIVITY",
            "args": {
                "pid": os.getpid(),
                "activity": activity,
            },
            "nonce": str(uuid.uuid4()),
        }
        data = json.dumps(payload).encode("utf-8")
        packet = struct.pack("<II", OP_FRAME, len(data)) + data
        try:
            self.sock.settimeout(timeout)
            self.sock.sendall(packet)
            try:
                self._recv(self.sock, timeout=timeout)
            except Exception:
                pass
            self.last_update_ok = True
            self.last_update_at = time.time()
            self.last_error = ""
            return True
        except Exception as e:
            self.last_update_ok = False
            self.last_error = str(e)
            self.close()
            return False

    def clear(self) -> bool:
        ok = self.send_activity(None)
        self.close()
        return ok


def build_activity(
    ai_name: str, cfg: DiscordConfig, now: float | None = None
) -> dict[str, Any]:
    """Build the Rich Presence payload.

    ``details`` rotates through :data:`ACTIVITY_PHRASES` once per wall-clock
    minute. Pass ``now`` (epoch seconds) to make the rotation deterministic in
    tests; the live app lets the CLI refresh presence each minute.
    """
    name = (ai_name or "0rb1t").strip() or "0rb1t"
    stamp = time.time() if now is None else now
    phrase = ACTIVITY_PHRASES[int(stamp // 60) % len(ACTIVITY_PHRASES)]
    return {
        "details": phrase.format(name=name),
        "state": REPO_URL,
        "assets": {
            "large_image": cfg.large_image or "orb1t",
            "large_text": cfg.large_text or "0rb1t",
        },
        "buttons": [
            {"label": "GitHub", "url": f"https://{REPO_URL}"},
        ],
        "instance": False,
    }
