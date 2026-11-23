"""Compatibility backend wrapper around engine adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .engines.opencode import OpenCodeEngine
from .engines.base import EngineRequest
from .errors import EngineError


class BackendError(RuntimeError):
    """Legacy stringly error for backward compatibility."""

    def __init__(self, message: str, *, cause: EngineError | None = None):
        super().__init__(message)
        self.cause = cause


@dataclass
class Reply:
    text: str = ""
    session_id: str | None = None
    error: str | None = None


def opencode_path() -> str | None:
    eng = OpenCodeEngine()
    return eng.command if eng.is_available() else None


def ensure_opencode() -> str:
    eng = OpenCodeEngine()
    try:
        eng.ensure_available()
    except EngineError as e:
        raise BackendError(str(e), cause=e) from e
    return eng.command


def send(
    message: str,
    *,
    session_id: str | None = None,
    cwd: str | None = None,
    on_text: Callable[[str], None] | None = None,
) -> Reply:
    """Legacy helper used by existing callers."""
    _ = on_text
    eng = OpenCodeEngine()
    try:
        resp = eng.send(EngineRequest(message=message, session_id=session_id, cwd=cwd))
    except EngineError as e:
        raise BackendError(str(e), cause=e) from e
    return Reply(text=resp.text, session_id=resp.session_id, error=resp.error)
