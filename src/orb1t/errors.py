"""Error types for 0rb1t."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class Orb1tError(Exception):
    """Base error for 0rb1t."""


class ConfigError(Orb1tError):
    pass


class PluginError(Orb1tError):
    pass


class CommandError(Orb1tError):
    pass


class WorkflowError(Orb1tError):
    pass


@dataclass
class EngineError(Orb1tError):
    """Normalized engine error."""

    message: str
    code: str = "engine_error"
    engine: str | None = None
    capability: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        Orb1tError.__init__(self, self.message)

    def __str__(self) -> str:
        prefix = f"[{self.engine}] " if self.engine else ""
        cap = f" ({self.capability})" if self.capability else ""
        return f"{prefix}{self.message}{cap}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "code": self.code,
            "engine": self.engine,
            "capability": self.capability,
            "detail": dict(self.detail),
        }


class UnsupportedCapabilityError(EngineError):
    def __init__(self, engine: str, capability: str, message: str | None = None):
        super().__init__(
            message=message or f"Capability '{capability}' is not supported by engine '{engine}'",
            code="unsupported_capability",
            engine=engine,
            capability=capability,
        )


class EngineUnavailableError(EngineError):
    def __init__(self, engine: str, message: str, detail: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            code="engine_unavailable",
            engine=engine,
            detail=dict(detail or {}),
        )
