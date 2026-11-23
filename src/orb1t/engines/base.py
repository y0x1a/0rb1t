"""Engine adapter contract and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..errors import UnsupportedCapabilityError


CAPABILITIES = (
    "health",
    "models",
    "agents",
    "sessions.list",
    "sessions.create",
    "sessions.delete",
    "send",
    "stream",
    "cancel",
)


@dataclass
class EngineCapabilities:
    values: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def from_list(cls, supported: list[str] | tuple[str, ...]) -> "EngineCapabilities":
        vals = {k: False for k in CAPABILITIES}
        for k in supported:
            if k in vals:
                vals[k] = True
        return cls(vals)

    def supports(self, capability: str) -> bool:
        return bool(self.values.get(capability, False))

    def declared(self) -> dict[str, bool]:
        return {k: bool(self.values.get(k, False)) for k in CAPABILITIES}

    def supported_list(self) -> list[str]:
        return [k for k, v in self.declared().items() if v]


@dataclass
class EngineHealth:
    ok: bool
    installed: bool
    message: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineRequest:
    message: str
    session_id: str | None = None
    cwd: str | None = None
    model: str | None = None
    agent: str | None = None
    system_prompt: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineResponse:
    text: str = ""
    session_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class SessionInfo:
    id: str
    title: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class EngineAdapter(ABC):
    """Base engine adapter. Engines must declare capabilities explicitly."""

    name: str = "engine"

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities.from_list([])

    def supports(self, capability: str) -> bool:
        return self.capabilities().supports(capability)

    def require(self, capability: str) -> None:
        if not self.supports(capability):
            raise UnsupportedCapabilityError(self.name, capability)

    @abstractmethod
    def health(self) -> EngineHealth: ...

    def info(self) -> dict[str, Any]:
        h = self.health()
        caps = self.capabilities().declared()
        return {
            "name": self.name,
            "installed": h.installed,
            "healthy": h.ok,
            "status": h.message,
            "capabilities": caps,
        }

    @abstractmethod
    def send(self, request: EngineRequest) -> EngineResponse: ...

    def list_models(self) -> list[str]:
        self.require("models")
        raise UnsupportedCapabilityError(self.name, "models")

    def list_agents(self) -> list[str]:
        self.require("agents")
        raise UnsupportedCapabilityError(self.name, "agents")

    def list_sessions(self, cwd: str | None = None) -> list[SessionInfo]:
        self.require("sessions.list")
        raise UnsupportedCapabilityError(self.name, "sessions.list")

    def create_session(self, cwd: str | None = None) -> SessionInfo:
        self.require("sessions.create")
        raise UnsupportedCapabilityError(self.name, "sessions.create")

    def delete_session(self, session_id: str, cwd: str | None = None) -> bool:
        self.require("sessions.delete")
        raise UnsupportedCapabilityError(self.name, "sessions.delete")

    def cancel(self, session_id: str, cwd: str | None = None) -> bool:
        self.require("cancel")
        raise UnsupportedCapabilityError(self.name, "cancel")

    def shutdown(self) -> None:
        """Optional lifecycle hook for adapters holding resources."""
        return None
