"""Simple lifecycle hook system."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable


Hook = Callable[[dict[str, Any]], Any]


@dataclass
class HookResult:
    name: str
    handler: str
    ok: bool
    error: str | None = None


class EventBus:
    def __init__(self) -> None:
        self._hooks: dict[str, list[tuple[str, Hook]]] = defaultdict(list)

    def on(self, event: str, hook: Hook, *, source: str = "unknown") -> None:
        self._hooks[event].append((source, hook))

    def emit(self, event: str, payload: dict[str, Any] | None = None) -> list[HookResult]:
        data = dict(payload or {})
        results: list[HookResult] = []
        for source, hook in list(self._hooks.get(event, [])):
            try:
                hook(data)
                results.append(HookResult(event, source, True))
            except Exception as e:  # plugin isolation
                results.append(HookResult(event, source, False, str(e)))
        return results

    def clear(self) -> None:
        self._hooks.clear()


HOOK_EVENTS = [
    "app.start",
    "app.exit",
    "session.start",
    "session.new",
    "message.before",
    "message.after",
    "command.before",
    "command.after",
    "config.loaded",
    "plugins.loaded",
]
