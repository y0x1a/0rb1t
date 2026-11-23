"""Engine adapter registry."""

from __future__ import annotations

from typing import Any, Callable

from ..errors import EngineError
from .base import EngineAdapter
from .opencode import OpenCodeEngine


EngineFactory = Callable[[dict[str, Any]], EngineAdapter]


def _build_opencode(config: dict[str, Any]) -> EngineAdapter:
    ecfg = config.get("engine", {}) if isinstance(config.get("engine"), dict) else {}
    return OpenCodeEngine(
        command=str(ecfg.get("command", "opencode")),
        auto=bool(ecfg.get("auto", True)),
    )


_REGISTRY: dict[str, EngineFactory] = {
    "opencode": _build_opencode,
}


def available_engines() -> list[str]:
    return sorted(_REGISTRY.keys())


def build_engine(config: dict[str, Any]) -> EngineAdapter:
    ecfg = config.get("engine", {}) if isinstance(config.get("engine"), dict) else {}
    name = str(ecfg.get("name", "opencode")).lower().strip() or "opencode"

    factory = _REGISTRY.get(name)
    if factory is None:
        raise EngineError(
            f"Unknown engine '{name}'. Available engines: {', '.join(available_engines())}",
            code="unknown_engine",
            engine=name,
        )
    return factory(config)


def register_engine(name: str, factory: EngineFactory) -> None:
    """Register an engine adapter factory. Intended for internal/tests/extensions."""
    key = name.lower().strip()
    if not key:
        raise ValueError("engine name required")
    _REGISTRY[key] = factory


def unregister_engine(name: str) -> None:
    key = name.lower().strip()
    _REGISTRY.pop(key, None)
