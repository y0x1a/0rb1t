"""OpenCode engine adapter."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from ..errors import EngineError, EngineUnavailableError
from .base import EngineCapabilities, EngineHealth, EngineRequest, EngineResponse, SessionInfo


class OpenCodeEngine:
    name = "opencode"

    def __init__(self, command: str = "opencode", auto: bool = True) -> None:
        self.command = command
        self.auto = auto
        self._active_procs: dict[str, subprocess.Popen[str]] = {}

    # --- capabilities / lifecycle ---
    def capabilities(self) -> EngineCapabilities:
        # Explicit and conservative. OpenCode CLI supports more, but only declare
        # what this adapter implements reliably right now.
        return EngineCapabilities.from_list(["health", "send", "sessions.list"])

    def supports(self, capability: str) -> bool:
        return self.capabilities().supports(capability)

    def require(self, capability: str) -> None:
        from ..errors import UnsupportedCapabilityError

        if not self.supports(capability):
            raise UnsupportedCapabilityError(self.name, capability)

    def is_available(self) -> bool:
        return shutil.which(self.command) is not None

    def health(self) -> EngineHealth:
        path = shutil.which(self.command)
        if not path:
            return EngineHealth(
                ok=False,
                installed=False,
                message=f"{self.command} not found on PATH",
                detail={"command": self.command},
            )
        try:
            proc = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except Exception as e:
            return EngineHealth(
                ok=False,
                installed=True,
                message=f"failed to run {self.command} --version: {e}",
                detail={"command": self.command, "path": path},
            )
        out = (proc.stdout or proc.stderr or "").strip()
        ok = proc.returncode == 0
        return EngineHealth(
            ok=ok,
            installed=True,
            message=out or ("ok" if ok else f"exit {proc.returncode}"),
            detail={"command": self.command, "path": path, "returncode": proc.returncode},
        )

    def ensure_available(self) -> None:
        h = self.health()
        if not h.installed:
            raise EngineUnavailableError(
                self.name,
                f"{self.command} is not installed or not on PATH. Install it from https://opencode.ai and try again.",
                detail=h.detail,
            )
        if not h.ok:
            raise EngineUnavailableError(self.name, h.message or "engine unhealthy", detail=h.detail)

    def info(self) -> dict[str, Any]:
        h = self.health()
        return {
            "name": self.name,
            "command": self.command,
            "auto": self.auto,
            "installed": h.installed,
            "healthy": h.ok,
            "status": h.message,
            "capabilities": self.capabilities().declared(),
        }

    # --- core messaging ---
    def send(self, request: EngineRequest) -> EngineResponse:
        self.require("send")
        h = self.health()
        if not h.installed:
            raise EngineUnavailableError(
                self.name,
                f"{self.command} is not installed or not on PATH. Install it from https://opencode.ai and try again.",
                detail=h.detail,
            )

        cmd = [self.command, "run", "--format", "json"]
        if self.auto:
            cmd.append("--auto")
        if request.session_id:
            cmd += ["--session", request.session_id]
        if request.model:
            cmd += ["--model", request.model]
        if request.agent:
            cmd += ["--agent", request.agent]

        message = request.message
        if request.system_prompt:
            message = f"<persona>\n{request.system_prompt}\n</persona>\n\n{request.message}"
        cmd += ["--", message]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=request.cwd,
                bufsize=1,
            )
        except OSError as e:
            raise EngineError(f"failed to start {self.command}: {e}", code="engine_start_failed", engine=self.name) from e

        resp = EngineResponse()
        text_chunks: list[tuple[str, str]] = []

        assert proc.stdout is not None
        assert proc.stderr is not None
        try:
            for raw in proc.stdout:
                line = raw.rstrip("\n")
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                etype = event.get("type")
                part = event.get("part") or {}
                session = event.get("sessionID") or part.get("sessionID")
                if session and not resp.session_id:
                    resp.session_id = session
                    self._active_procs[session] = proc
                if etype == "text" and isinstance(part.get("text"), str):
                    pid = part.get("id") or str(len(text_chunks))
                    text_chunks.append((pid, part["text"]))
                elif etype == "error":
                    err = part.get("error") or event.get("error") or "unknown error"
                    resp.error = err if isinstance(err, str) else json.dumps(err)
        finally:
            proc.stdout.close()
            stderr = proc.stderr.read()
            proc.stderr.close()
            proc.wait()
            if resp.session_id:
                self._active_procs.pop(resp.session_id, None)

        latest: dict[str, str] = {}
        order: list[str] = []
        for pid, text in text_chunks:
            if pid not in latest:
                order.append(pid)
            latest[pid] = text
        resp.text = "\n".join(latest[pid] for pid in order if latest[pid]).strip()

        if proc.returncode != 0 and not resp.text:
            msg = resp.error or stderr.strip() or f"{self.command} exited with code {proc.returncode}"
            raise EngineError(msg, code="engine_process_failed", engine=self.name, detail={"returncode": proc.returncode})
        if resp.error and not resp.text:
            raise EngineError(resp.error, code="engine_response_error", engine=self.name)
        resp.raw = {"returncode": proc.returncode}
        return resp

    # --- optional capabilities ---
    def list_sessions(self, cwd: str | None = None) -> list[SessionInfo]:
        self.require("sessions.list")
        h = self.health()
        if not h.installed:
            raise EngineUnavailableError(self.name, f"{self.command} not found on PATH", detail=h.detail)
        try:
            proc = subprocess.run(
                [self.command, "session", "list", "--format", "json"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except Exception as e:
            raise EngineError(f"failed to list sessions: {e}", code="engine_session_list_failed", engine=self.name) from e

        if proc.returncode != 0:
            # Some CLI versions may not support --format json; fail clearly.
            msg = (proc.stderr or proc.stdout or "").strip() or f"session list failed ({proc.returncode})"
            raise EngineError(msg, code="engine_session_list_failed", engine=self.name, detail={"returncode": proc.returncode})

        raw = (proc.stdout or "").strip()
        try:
            data = json.loads(raw) if raw else []
        except json.JSONDecodeError as e:
            raise EngineError(
                "session list returned non-JSON output; adapter cannot parse it",
                code="engine_session_parse_failed",
                engine=self.name,
                detail={"output": raw[:500]},
            ) from e

        items = data if isinstance(data, list) else data.get("sessions", []) if isinstance(data, dict) else []
        out: list[SessionInfo] = []
        for it in items:
            if isinstance(it, dict):
                sid = str(it.get("id") or it.get("sessionID") or "").strip()
                if sid:
                    out.append(SessionInfo(id=sid, title=it.get("title"), raw=it))
        return out

    def shutdown(self) -> None:
        for proc in list(self._active_procs.values()):
            try:
                proc.terminate()
            except Exception:
                pass
        self._active_procs.clear()
